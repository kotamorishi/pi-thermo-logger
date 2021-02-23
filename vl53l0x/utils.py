#
# utils.py contains a set of helper functions
#

def make_uint16(lsb, msb):
    """make a meaningful uint16 out of LSB and MSB"""
    return (msb << 8) + lsb
