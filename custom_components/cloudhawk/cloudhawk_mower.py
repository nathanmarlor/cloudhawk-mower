#!/usr/bin/env python3
from __future__ import annotations

"""
CloudHawk Lawn Mower Bluetooth Library - Simple Version
=====================================

Complete reverse-engineered protocol for CloudHawk lawn mowers.
Successfully tested with SN0190104721 running firmware RM V6.01_2021(241131)B

Features:
- Full mower control (start, stop, dock)
- Battery level and charging status
- Signal strength monitoring
- Date/time synchronization
- Settings management
- Schedule control
- Historical data retrieval
- Fault record access

Protocol: 55AA + length + 80 + command + payload + checksum

Simplified Command-Response Model:
- Commands are sent without waiting for specific responses
- All responses are captured by the constant listener and stored
- Data is retrieved from the response store when needed
- Responses may arrive out of order or with delays
"""

import asyncio
import logging
import struct
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, date, time
from dataclasses import dataclass, field
from enum import Enum
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

class MowerState(Enum):
    """Simple mower operational states"""
    UNKNOWN = "unknown"
    IDLE = "idle"
    MOWING = "mowing"
    DOCKED = "docked"
    RETURNING = "returning"
    STOPPED = "stopped"
    ERROR = "error"


class SignalType(Enum):
    """Boundary signal selection"""
    S1 = 1
    S2 = 2
    S3 = 3


@dataclass
class FaultRecord:
    """Fault/error record"""
    timestamp: datetime
    error_code: int
    description: str = ""

@dataclass
class MowerInfo:
    """Complete mower information"""
    serial_number: str = ""
    firmware_version: str = ""
    battery_level: int = 0
    is_charging: bool = False
    signal_type: SignalType = SignalType.S1
    trimming_enabled: bool = False
    current_date: Optional[date] = None
    current_time: Optional[time] = None
    has_schedule: bool = False
    status: MowerState = MowerState.UNKNOWN
    fault_records: List[FaultRecord] = field(default_factory=list)

class CloudHawkMower:
    """Complete CloudHawk Lawn Mower Controller with decoded protocol"""
    
    # Service and Characteristic UUIDs (from decompiled LawnMowerBLEHandler.kt)
    SERVICE_UUID = "0000ff12-0000-1000-8000-00805f9b34fb"
    WRITE_CHARACTERISTIC_UUID = "0000ff01-0000-1000-8000-00805f9b34fb" 
    NOTIFY_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
    
    # SUMIC alternative UUIDs
    SUMIC_SERVICE_UUID = "0000abf0-0000-1000-8000-00805f9b34fb"
    SUMIC_WRITE_UUID = "0000abf4-0000-1000-8000-00805f9b34fb"
    SUMIC_NOTIFY_UUID = "0000abf3-0000-1000-8000-00805f9b34fb"
    
    # Protocol constants - Updated based on HCI analysis
    HEAD_BYTES = "55AA"
    BLE_C1 = "80"  # BLE command prefix
    
    
    # Command definitions (from decompiled LawnMowerCommand.kt)
    class Commands:
        # Control Commands
        START = "05"                    # Regular start
        START_ONCE = "7D"              # Start once  
        STOP = "29"                    # Stop mowing
        CHARGE = "06"                  # Return to charge
        RESET = "0F"                   # Reset device
        SPIRAL_CUT = "79"              # Spiral cutting pattern
        EDGE_CUT_ONCE = "7c"           # Edge cutting along boundaries
        
        # Info Commands
        GET_FIRMWARE = "01"            # Get firmware version
        GET_SERIAL = "02"              # Get serial number
        GET_DEVICE_STATUS = "0201"     # Get device status
        GET_STATUS = "81"              # Get status (from 8081 responses)
        GET_SIGNAL = "0b"              # Get signal strength
        GET_BATTERY = "83"             # Get battery info
        
        # Settings Commands
        GET_CUT_WIDTH = "09"           # Get cut width
        GET_TRIMMING = "07"            # Get trimming settings
        GET_RAIN_SETTINGS = "20"       # Get rain settings
        GET_RAIN_DELAY = "32"          # Get rain delay time
        GET_ULTRASONIC_DISTANCE = "56" # Get ultrasonic distance
        GET_ULTRASONIC_STATUS = "54"   # Get ultrasonic on/off
        
        # Schedule Commands
        GET_CUT_DAY = "11"             # Get cut day schedule
        GET_CUT_SCHEDULE = "70"        # Get cut time schedule
        SET_CUT_SCHEDULE = "71"        # Set cut time schedule
        
        # System Commands
        GET_SYSTEM_DATE = "19"         # Get system date
        GET_SYSTEM_TIME = "1b"         # Get system time
        SET_SYSTEM_DATE = "1a"         # Set system date
        SET_SYSTEM_TIME = "1c"         # Set system time
        GET_LANGUAGE = "1d"            # Get language setting
        
        # Security Commands
        GET_PIN = "03"                 # Get PIN code
        GET_PUK = "31"                 # Get PUK code
        
        # Records Commands
        GET_WORKING_TIME = "7a"        # Get working time
        GET_HEALTH_RECORD = "18"       # Get health record
        GET_FAULT_RECORD = "15"        # Get fault record
        GET_CUTTING_RECORD = "16"      # Get cutting record
        GET_CHARGING_RECORD = "17"     # Get charging record
        
    
    def __init__(self, device_name: str = "SN0190104721", timeout: float = 10.0):
        self.device_name = device_name
        self.timeout = timeout
        self.client: Optional[BleakClient] = None
        self.response_data: Dict[str, Any] = {}
        self.write_char = None
        self.notify_char = None
        self.mower_info = MowerInfo()
        
        # Central response store for all mower data
        self.response_store: Dict[str, Any] = {}
        self._listener_active = False
        
        # Callback for notifying when new data arrives
        self.data_update_callback: Optional[Callable] = None
        
        # Connection maintenance
        self._connection_maintenance_task: Optional[asyncio.Task] = None
        self._maintenance_active = False
    
    def set_data_update_callback(self, callback: Callable):
        """Set callback to be called when new data arrives from mower"""
        self.data_update_callback = callback
    
    def _get_command_name(self, command_code: str) -> str:
        """Get command name from command code for logging"""
        # Find the attribute name that matches the command code
        for attr_name in dir(self.Commands):
            if not attr_name.startswith('_') and getattr(self.Commands, attr_name) == command_code:
                return attr_name
        return f"UNKNOWN({command_code})"
    
    def generate_command(self, command_code: str, content: str = "") -> bytes:
        """Generate a properly formatted CloudHawk command
        
        Based on decompiled CloudHawk code analysis (LawnMowerCommand.generateCommand):
        - Format: 55AA + [length] + [command] + [data] + [checksum]
        - Length: Number of bytes in command + data (not including header and checksum)
        - Checksum: Sum of all bytes (including header) modulo 256
        """
        # Build command with BLE prefix if needed
        if len(command_code) == 2:
            full_command = self.BLE_C1 + command_code
        else:
            full_command = command_code
            
        # Calculate length in bytes
        command_bytes = len(full_command) // 2
        content_bytes = len(content) // 2 if content else 0
        total_length = command_bytes + content_bytes
        
        # Format: 55AA + length + command + content (before checksum)
        length_hex = f"{total_length:02X}"
        command_string = self.HEAD_BYTES + length_hex + full_command + content
        
        # Calculate checksum: sum of all bytes modulo 256 (as per TypeConverters.makeChecksum)
        command_bytes_array = bytes.fromhex(command_string)
        checksum = sum(command_bytes_array) % 256
        checksum_hex = f"{checksum:02X}"
        
        # Final command with checksum
        final_command = command_string + checksum_hex
        
        return bytes.fromhex(final_command)
    
    async def scan_for_mower(self, scan_time: float = 10.0) -> Optional[str]:
        """Scan for CloudHawk mower and return its address"""
        logger.info(f"Scanning for {self.device_name} mower...")
        
        devices = await BleakScanner.discover(timeout=scan_time)
        
        for device in devices:
            if device.name and self.device_name in device.name:
                logger.info(f"Found mower: {device.name} ({device.address})")
                return device.address
                
        logger.warning("No CloudHawk mower found")
        return None
    
    async def connect(self, address: Optional[str] = None) -> bool:
        """Connect to the mower"""
        if not address:
            address = await self.scan_for_mower()
            if not address:
                return False
        
        try:
            logger.info(f"Connecting to mower at {address}...")
            self.client = BleakClient(address, timeout=self.timeout)
            await self.client.connect()
            
            # Find the correct service and characteristics
            services = self.client.services
            
            # Try main service first
            service = services.get_service(self.SERVICE_UUID)
            if service:
                self.write_char = service.get_characteristic(self.WRITE_CHARACTERISTIC_UUID)
                self.notify_char = service.get_characteristic(self.NOTIFY_CHARACTERISTIC_UUID)
            else:
                # Try SUMIC service
                service = services.get_service(self.SUMIC_SERVICE_UUID)
                if service:
                    self.write_char = service.get_characteristic(self.SUMIC_WRITE_UUID)
                    self.notify_char = service.get_characteristic(self.SUMIC_NOTIFY_UUID)
            
            if not self.write_char or not self.notify_char:
                logger.error("Could not find required characteristics")
                await self.disconnect()
                return False
            
            logger.info("Successfully connected to mower")
            
            # Start background connection maintenance
            self._start_connection_maintenance()

            # Start constant listener and populate initial data
            await self.start_constant_listener()
            await self.populate_initial_data()
                   
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the mower"""
        if self.is_connected():
            try:
                await self.stop_constant_listener()
                await self.client.disconnect()
                logger.info("Disconnected from mower")
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            finally:
                self.client = None
                self._listener_active = False
        
        # Stop connection maintenance
        self._stop_connection_maintenance()
    
    def is_connected(self) -> bool:
        """Check if currently connected to the mower"""
        return self.client is not None and self.client.is_connected
    
    def _start_connection_maintenance(self):
        """Start background connection maintenance task"""
        if self._maintenance_active:
            return
        
        self._maintenance_active = True
        self._connection_maintenance_task = asyncio.create_task(self._connection_maintenance_loop())
        logger.info("Started connection maintenance")
    
    def _stop_connection_maintenance(self):
        """Stop background connection maintenance task"""
        self._maintenance_active = False
        if self._connection_maintenance_task:
            self._connection_maintenance_task.cancel()
            self._connection_maintenance_task = None
        logger.info("Stopped connection maintenance")
    
    async def _connection_maintenance_loop(self):
        """Background task to maintain connection to mower"""
        while self._maintenance_active:
            try:            
                if self._maintenance_active and not self.is_connected():
                    logger.warning("Connection lost, attempting to reconnect")
                    # Try to reconnect (will use the last known address)
                    if await self.connect():
                        logger.info("Connection successful")
                    else:
                        logger.warning("Connection failed, will retry in 5 seconds")
                
                await asyncio.sleep(5)  # Check every 30 seconds
            except asyncio.CancelledError:
                logger.debug("Connection maintenance task cancelled")
                break
            except Exception as ex:
                logger.error(f"Error in connection maintenance, will retry in 10 seconds: {ex}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def start_constant_listener(self):
        """Start the constant notification listener to capture all responses"""
        if self._listener_active or not self.is_connected():
            return
            
        self._listener_active = True
        logger.info("Starting constant notification listener")
        
        def notification_handler(sender, data):
            hex_data = data.hex()
            logger.debug(f"Notification received: {hex_data}")
            
            # Parse 55AA protocol response
            if len(data) >= 3 and data[0] == 0x55 and data[1] == 0xAA:
                length = data[2]
                payload = data[3:3+length] if len(data) > 3 else b''
                
                if len(payload) >= 2:
                    command_response = payload[0]
                    status = payload[1]
                    data_part = payload[2:] if len(payload) > 2 else b''
                    
                    # Store response by command type
                    command_type = f"{command_response:02x}{status:02x}"
                    self.response_store[command_type] = {
                        'timestamp': datetime.now(),
                        'payload': payload,
                        'data': data_part,
                        'raw_data': data,
                        'hex': hex_data
                    }
                    
                    # Get command name for logging
                    command_name = self._get_command_name(f"{status:02x}")
                    logger.debug(f"Received {command_name} notification: {data_part.hex()}")
                    
                    # Trigger callback to notify HA of new data
                    if self.data_update_callback:
                        try:
                            self.data_update_callback()
                        except Exception as e:
                            logger.error(f"Error in data update callback: {e}")
        
        # Start notifications
        await self.client.start_notify(self.notify_char, notification_handler)
        logger.info("Constant listener started")
    
    async def stop_constant_listener(self):
        """Stop the constant notification listener"""
        if self._listener_active and self.client and self.notify_char:
            await self.client.stop_notify(self.notify_char)
            self._listener_active = False
            logger.info("Constant listener stopped")
    
    async def send_command(self, command: bytes) -> bool:
        """Send a command to the mower without waiting for response"""
        if not self.is_connected() or not self.write_char:
            logger.error("Not connected to mower")
            return False
        
        # Extract command code for logging
        command_hex = command.hex()
        command_code = command_hex[8:10]  # Get command code (e.g., 07)
        command_name = self._get_command_name(command_code)
        
        try:
            # Send command
            await self.client.write_gatt_char(self.write_char, command)
            logger.debug(f"Sent {command_name} command ({command_code})")
            return True
            
        except Exception as e:
            logger.error(f"Error sending {command_name} command: {e}")
            return False
    
    async def populate_initial_data(self):
        """Send commands to populate the response store with initial mower data"""
        logger.info("Sending initial data commands...")
        
        # Commands to get initial data (excluding date/time as requested)
        initial_commands = [
            ("firmware", self.Commands.GET_FIRMWARE),
            ("serial", self.Commands.GET_SERIAL),
            ("battery", self.Commands.GET_BATTERY),
            ("signal", self.Commands.GET_SIGNAL),
            ("trimming", self.Commands.GET_TRIMMING),
            ("schedule", self.Commands.GET_CUT_SCHEDULE),
            ("fault_records", self.Commands.GET_FAULT_RECORD),
        ]
        
        for name, command_code in initial_commands:
            try:
                command = self.generate_command(command_code)
                success = await self.send_command(command)
                if success:
                    logger.info(f"Sent {name} command")
                else:
                    logger.warning(f"Failed to send {name} command")
                # Small delay between commands
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error sending {name} command: {e}")
        
        logger.info("Initial data commands sent - responses will arrive asynchronously")
    
    def get_battery_data(self) -> Optional[Dict[str, Any]]:
        """Get battery data from store"""
        return self.response_store.get("8083")
    
    def get_serial_data(self) -> Optional[Dict[str, Any]]:
        """Get serial number data from store"""
        return self.response_store.get("8002")
    
    def get_firmware_data(self) -> Optional[Dict[str, Any]]:
        """Get firmware data from store"""
        return self.response_store.get("8001")
    
    def get_signal_data(self) -> Optional[Dict[str, Any]]:
        """Get signal data from store"""
        return self.response_store.get("800b")
    
    def get_trimming_data(self) -> Optional[Dict[str, Any]]:
        """Get trimming data from store"""
        return self.response_store.get("8007")
    
    def get_schedule_data(self) -> Optional[Dict[str, Any]]:
        """Get schedule data from store"""
        return self.response_store.get("8070")
    
    def get_fault_records_data(self) -> Optional[Dict[str, Any]]:
        """Get fault records data from store"""
        return self.response_store.get("8015")
    
    def get_status_data(self) -> Optional[Dict[str, Any]]:
        """Get status data from store"""
        return self.response_store.get("8081")
    
    # === CONTROL METHODS ===
    
    async def start_mowing(self) -> bool:
        """Start regular mowing"""
        logger.info("Starting mowing...")
        command = self.generate_command(self.Commands.START)
        logger.debug(f"Start mowing command: {command.hex()}")
        
        success = await self.send_command(command)
        if success:
            logger.info("Start mowing command sent successfully")
        else:
            logger.error("Failed to send start mowing command")
        return success
    
    async def start_mowing_once(self) -> bool:
        """Start mowing once (instant mowing)"""
        logger.info("Starting mowing once...")
        command = self.generate_command(self.Commands.START_ONCE)
        logger.debug(f"Start mowing once command: {command.hex()}")
        
        success = await self.send_command(command)
        if success:
            logger.info("Start mowing once command sent successfully")
        else:
            logger.error("Failed to send start mowing once command")
        return success
    
    async def stop_mowing(self) -> bool:
        """Stop mowing"""
        logger.info("Stopping mowing...")
        command = self.generate_command(self.Commands.STOP)
        logger.debug(f"Stop mowing command: {command.hex()}")
        
        success = await self.send_command(command)
        if success:
            logger.info("Stop mowing command sent successfully")
        else:
            logger.error("Failed to send stop mowing command")
        return success
    
    async def return_to_dock(self) -> bool:
        """Return to charging dock"""
        logger.info("Returning to dock...")
        command = self.generate_command(self.Commands.CHARGE)
        logger.debug(f"Return to dock command: {command.hex()}")
        
        success = await self.send_command(command)
        if success:
            logger.info("Return to dock command sent successfully")
        else:
            logger.error("Failed to send return to dock command")
        return success
    
    async def start_spiral_cutting(self) -> bool:
        """Start spiral cutting pattern"""
        logger.info("Starting spiral cutting...")
        command = self.generate_command(self.Commands.SPIRAL_CUT)
        logger.debug(f"Start spiral cutting command: {command.hex()}")
        
        success = await self.send_command(command)
        if success:
            logger.info("Start spiral cutting command sent successfully")
        else:
            logger.error("Failed to send start spiral cutting command")
        return success
    
    async def start_edge_cutting(self) -> bool:
        """Start edge cutting along boundaries"""
        logger.info("Starting edge cutting...")
        command = self.generate_command(self.Commands.EDGE_CUT_ONCE)
        logger.debug(f"Start edge cutting command: {command.hex()}")
        
        success = await self.send_command(command)
        if success:
            logger.info("Start edge cutting command sent successfully")
        else:
            logger.error("Failed to send start edge cutting command")
        return success

    # === INFORMATION PARSING METHODS ===
    
    def _parse_date(self, payload: bytes) -> Optional[date]:
        """Parse date from payload: 801907e90915 -> 2025-09-21"""
        if len(payload) >= 6:
            try:
                year = int.from_bytes(payload[2:4], 'big')  # 07e9 = 2025
                month = payload[4]  # 09
                day = payload[5]    # 15 = 21
                return date(year, month, day)
            except:
                pass
        return None
    
    def _parse_time(self, payload: bytes) -> Optional[time]:
        """Parse time from payload: 801b0b33 -> 11:51"""
        if len(payload) >= 4:
            try:
                hour = payload[2]     # 0b = 11
                minute = payload[3]   # 33 = 51
                return time(hour, minute)
            except:
                pass
        return None
    
    def _parse_battery(self, payload: bytes) -> tuple[int, bool]:
        """Parse battery level and charging status: 80830000cd640004 -> 100%, charging"""
        battery_level = 0
        is_charging = False
        
        if len(payload) >= 8:
            # Battery level at position 5: cd=205, 64=100
            battery_level = payload[5]  # 64 = 100%
            # Charging status at end: 0004 -> 04 = charging
            if len(payload) >= 8:
                is_charging = payload[7] == 0x04
                
        return battery_level, is_charging
    
    def _parse_signal_type(self, payload: bytes) -> SignalType:
        """Parse signal selection: 800b02 -> S2"""
        if len(payload) >= 3:
            signal_val = payload[2]  # 02 = S2
            if signal_val in [1, 2, 3]:
                return SignalType(signal_val)
        return SignalType.S1
    
    def _parse_trimming_enabled(self, payload: bytes) -> bool:
        """Parse trimming status: 800701 -> enabled"""
        if len(payload) >= 3:
            return payload[2] == 0x01
        return False
    
    def _parse_schedule_data(self, payload: bytes) -> bool:
        """Parse schedule data: all zeros = no schedule"""
        if len(payload) > 2:
            # Check if all data bytes are zero
            data_part = payload[2:]
            return not all(b == 0 for b in data_part)
        return False
    
    def _parse_status(self, payload: bytes) -> MowerState:
        """Parse mower status from 8081 payload"""
        if len(payload) >= 3:
            status_byte = payload[2]  # Status byte is at position 2
            if status_byte == 0x01:
                return MowerState.RETURNING
            elif status_byte == 0x38:
                return MowerState.MOWING
            elif status_byte == 0x0b:
                return MowerState.DOCKED
            elif status_byte == 0x0e:
                return MowerState.STOPPED
        
        # Default to unknown if no status matches
        return MowerState.UNKNOWN
    
    def _parse_fault_records(self, payload: bytes) -> List[FaultRecord]:
        """Parse fault record data"""
        records = []
        if len(payload) > 2:
            # Fault records contain timestamp and error code data
            # Format appears to be: year(2) month(1) day(1) hour(1) min(1) error(1)
            data = payload[2:]
            i = 0
            while i + 6 < len(data):
                try:
                    year = int.from_bytes(data[i:i+2], 'big')
                    month = data[i+2]
                    day = data[i+3]
                    hour = data[i+4]
                    minute = data[i+5]
                    error_code = data[i+6]
                    
                    timestamp = datetime(year, month, day, hour, minute)
                    records.append(FaultRecord(timestamp, error_code))
                    i += 7
                except:
                    break
        return records

    # === HIGH-LEVEL INFORMATION METHODS ===
    
    async def get_mower_info(self) -> MowerInfo:
        """Get complete mower information from the response store"""
        info = MowerInfo()
        
        # Get serial number from store
        serial_data = self.get_serial_data()
        if serial_data and serial_data.get('data'):
            info.serial_number = serial_data['data'].decode('ascii', errors='ignore').strip()
            logger.debug(f"Serial number: {info.serial_number}")
        
        # Get firmware from store
        firmware_data = self.get_firmware_data()
        if firmware_data and firmware_data.get('data'):
            fw_bytes = firmware_data['data']
            info.firmware_version = fw_bytes.decode('ascii', errors='ignore').strip()
            logger.debug(f"Firmware: {info.firmware_version}")
        
        # Get battery info from store
        battery_data = self.get_battery_data()
        if battery_data and battery_data.get('payload'):
            payload = battery_data['payload']
            battery_level, is_charging = self._parse_battery(payload)
            info.battery_level = battery_level
            info.is_charging = is_charging
            logger.debug(f"Battery: {battery_level}%, Charging: {is_charging}")
        
        # Get signal type from store
        signal_data = self.get_signal_data()
        if signal_data and signal_data.get('payload'):
            payload = signal_data['payload']
            signal_type = self._parse_signal_type(payload)
            info.signal_type = signal_type
            logger.debug(f"Signal type: {signal_type.name}")
        
        # Get trimming status from store
        trimming_data = self.get_trimming_data()
        if trimming_data and trimming_data.get('payload'):
            payload = trimming_data['payload']
            trimming_enabled = self._parse_trimming_enabled(payload)
            info.trimming_enabled = trimming_enabled
            logger.debug(f"Trimming: {'Enabled' if trimming_enabled else 'Disabled'}")
        
        # Get schedule status from store
        schedule_data = self.get_schedule_data()
        if schedule_data and schedule_data.get('payload'):
            payload = schedule_data['payload']
            has_schedule = self._parse_schedule_data(payload)
            info.has_schedule = has_schedule
            logger.debug(f"Schedule: {'Set' if has_schedule else 'None'}")
        
        # Get fault records from store
        fault_data = self.get_fault_records_data()
        if fault_data and fault_data.get('payload'):
            payload = fault_data['payload']
            fault_records = self._parse_fault_records(payload)
            info.fault_records = fault_records
            logger.debug(f"Fault records: {len(fault_records)} records")
        
        # Get mower status from store
        status_data = self.get_status_data()
        if status_data and status_data.get('payload'):
            payload = status_data['payload']
            status = self._parse_status(payload)
            info.status = status
            logger.debug(f"Status: {status.value}")
        
        logger.debug("Mower info collection completed")
        self.mower_info = info
        return info

# Example usage
async def main():
    """Example usage of the CloudHawk library"""
    mower = CloudHawkMower()
    
    try:
        # Connect
        if await mower.connect():
            logger.info("✅ Connected to mower")
            
            # Get complete mower information
            info = await mower.get_mower_info()
            print(f"📋 Mower Info:")
            print(f"   Serial: {info.serial_number}")
            print(f"   Firmware: {info.firmware_version}")
            print(f"   Battery: {info.battery_level}% {'(Charging)' if info.is_charging else ''}")
            print(f"   Signal: {info.signal_type.name}")
            print(f"   Trimming: {'Enabled' if info.trimming_enabled else 'Disabled'}")
            print(f"   Date: {info.current_date}")
            print(f"   Time: {info.current_time}")
            print(f"   Schedule: {'Set' if info.has_schedule else 'None'}")
            print(f"   Status: {info.status.value}")
            

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await mower.disconnect()

if __name__ == "__main__":
    asyncio.run(main())