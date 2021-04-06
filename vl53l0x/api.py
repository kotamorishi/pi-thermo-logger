#
# api.py contains a set of core functions
#

import smbus
import time

from vl53l0x.register import *
from vl53l0x.utils import *

class VL53L0X(object):
    def __init__(self, i2c_address=0x29):
        # i2c device address
        self.address = i2c_address

        # smbus object
        self.bus = smbus.SMBus(1)

        # static sequence config
        self.static_seq_config = 0

        # measurement data, in millimeter
        self.measurement = 0

    def setup(self):
        """configure the device when it first starts up"""
        self.data_init()
        self.static_init()
        self.perform_ref_calibration()
        self.perform_ref_spad_management()

    def measure(self):
        """start measuring and return its data"""
        self.perform_ref_signal_measurement()

        return self.measurement

    def data_init(self):
        """data initialization"""
        # set i2c standard mode
        self.write_byte(0x88, 0x00)

        # read whoami
        self.read_byte(0xC0)

        # use internal default settings
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)

        self.read_byte(0x91)

        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, 0xFF)

    def static_init(self):
        """static initialization"""
        self.write_byte(0xFF, 0x01)
        self.read_byte(0x84)
        self.write_byte(0xFF, 0x00)

        # read the sequence config and save it
        self.static_seq_config = self.read_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG)

    def perform_ref_calibration(self):
        """perform ref calibration, including vhv and phase one"""
        self.perform_vhv_calibration()
        self.perform_phase_calibration()

        # restore static sequence config
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, self.static_seq_config)

    def perform_vhv_calibration(self):
        """perform vhv calibration"""
        # run vhv
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, 0x01)

        self.perform_single_ref_calibration(0x40)

        # read vhv from device
        self.ref_calibration_io(0xCB)

        # restore static sequence config
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, self.static_seq_config)

    def perform_phase_calibration(self):
        """perform phase calibration"""
        # run phase cal
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, 0x02)

        self.perform_single_ref_calibration(0x0)

        # read phase cal from device
        self.ref_calibration_io(0xEE)

        # restore static sequence config
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, self.static_seq_config)

    def perform_single_ref_calibration(self, byte):
        """perform single ref calibration"""
        self.write_byte(VL53L0X_REG_SYSRANGE_START, VL53L0X_REG_SYSRANGE_MODE_START_STOP | byte)
        self.write_byte(VL53L0X_REG_SYSRANGE_START, 0x00)

    def ref_calibration_io(self, byte):
        """read vhv/phase calibration"""
        # read vhv from device
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0xFF, 0x00)

        self.read_byte(byte)

        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0xFF, 0x00)

    def perform_ref_spad_management(self):
        """perform ref spad management"""
        self.write_byte(0xFF, 0x01)
        self.write_byte(VL53L0X_REG_DYNAMIC_SPAD_REF_EN_START_OFFSET, 0x00)
        self.write_byte(VL53L0X_REG_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD, 0x2C)
        self.write_byte(0xFF, 0x00)
        self.write_byte(VL53L0X_REG_GLOBAL_CONFIG_REF_EN_START_SELECT, 0xB4)
        self.write_byte(VL53L0X_REG_POWER_MANAGEMENT_GO1_POWER_FORCE, 0)

        self.perform_ref_calibration()
        self.perform_ref_signal_measurement()

    def perform_ref_signal_measurement(self):
        """perform ref signal measurement"""
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, 0xC0)

        self.perform_single_ranging_measurement()

        self.write_byte(0xFF, 0x01)
        self.write_byte(0xFF, 0x00)

        # restore static sequence config
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, self.static_seq_config)

    def perform_single_ranging_measurement(self):
        """perform single ranging measurement and get its data"""
        self.perform_single_measurement()
        self.get_ranging_measurement_data()

    def perform_single_measurement(self):
        """perform single measurement"""
        self.start_measurement()

    def start_measurement(self):
        """start measurement"""
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)

        self.read_byte(0x91)

        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        # device mode single ranging
        self.write_byte(VL53L0X_REG_SYSRANGE_START, 0x01)

    def get_ranging_measurement_data(self):
        """get ranging measurement data"""
        raw_data = self.read_block(0x14)

        range_millimeter = make_uint16(raw_data[11], raw_data[10])
        signal_rate = make_uint16(raw_data[7], raw_data[6])
        ambient_rate = make_uint16(raw_data[9], raw_data[8])
        effective_spad_rtn_count = make_uint16(raw_data[3], raw_data[2])
        device_range_status = raw_data[0]

        #print("range: {}\tsignal rate: {}\tambient rate: {}\tspad count: {}\trange status: {}"
        #        .format(range_millimeter, signal_rate, ambient_rate, effective_spad_rtn_count, device_range_status))

        # update measurement
        self.measurement = range_millimeter

    def write_byte(self, reg, data):
        """write byte data to a given register address"""
        self.bus.write_byte_data(self.address, reg, data)

    def read_byte(self, reg):
        """read byte data from a given register address"""
        read = self.bus.read_byte_data(self.address, reg)

        return read

    def read_block(self, reg):
        """write i2c block data to a given register address"""
        read = self.bus.read_i2c_block_data(self.address, reg)

        return read
