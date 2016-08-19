import binascii
from struct import pack, pack_into, unpack


class MsgIntegrity(object):
    """A class for INTEGRITY message"""

    def __init__(self, hash_type=0):
        self.start_chunk = 0
        self.end_chunk = 0
        self.hash_type = hash_type
        self.hash_data = None
        
        if hash_type == 0:
            self.hash_len = 20 # SHA-1 20B
        elif hash_type == 1:
            self.hash_len = 28 # SHA-224 28B
        elif hash_type == 2:
            self.hash_len = 32 # SHA-256 32B
        elif hash_type == 3:
            self.hash_len = 48 # SHA-384 48B
        elif hash_type == 4:
            self.hash_len = 64 # SHA-512 64B


    def ParseReceivedData(self, data):
        """Parse binary data into object"""

        details = unpack('>II', data[0:8])
        self.start_chunk = details[0]
        self.end_chunk = details[1]

        self.hash_data = data[8:self.hash_len+8]

        return 8 + self.hash_len

    def __str__(self):
        return str("[INTEGRITY] Start: {0}; End: {1}; Hash Type: {2}; Hash Len: {3}; Hash: {4}"
                   .format(
                       self.start_chunk,
                       self.end_chunk,
                       self.hash_type,
                       len(self.hash_data),
                       binascii.hexlify(self.hash_data)))

    def __repr__(self):
        return self.__str__()
