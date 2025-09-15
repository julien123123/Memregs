import uctypes

'''
args structure: (name, length, bin=False, uctype format = None)
'''
class ucMemReg:
    def __init__(self, name, mem, memstart, *args, span=32):
        self.id = hash(args + tuple([memstart, span]))
        self.buf = mem[memstart:memstart + span]
        self.name = name
        self.mem = mem
        self.memstart = memstart
        self.span = span
        self.struct = {}
        self.layout = {}

        self._parse_args(args)
        self._make_struct()

    def __getitem__(self, it):
        return getattr(self.struct, it)

    def __setitem__(self, key, value):
        if type(value) in (str, bytes, bytearray):
            value = value.encode('utf-8') if type(value) is str else value
            for i in range(len(value)):
                self[key][i] = value[i]
        else:
            setattr(self.struct, key, value)

    def __str__(self):
        return '\n'.join(str(v)+": "+str(self[v]) for v in self.layout.keys())

    def _parse_args(self, ar):
        bit_pos = 0
        byte_pos = 0
        binl=[]
        l =[]
        for args in ar:
            if args[2]:
                binl.append(args)
            else:
                l.append(args)
        for dt in binl:
            name, ln, b, f = dt
            self.layout.update({name: byte_pos | bit_pos << uctypes.BF_POS | ln << uctypes.BF_LEN | uctypes.BFUINT8})
            bit_pos += ln
            if bit_pos >= 8:
                byte_pos += bit_pos // 8
                bit_pos = bit_pos % 8
        if bit_pos > 0:
            byte_pos += 1
            bit_pos = 0
        for dt in l:
            name, ln, b, fmt = dt
            if fmt:
                self.layout.update({name: byte_pos | fmt})
                print('he')
                
            else:
                if ln == 1:
                    self.layout.update({name: byte_pos | uctypes.UINT8})
                elif ln == 2:
                    self.layout.update({name: byte_pos | uctypes.UINT16})
                elif ln == 4:
                    self.layout.update({name: byte_pos | uctypes.UINT32})
                else:
                    self.layout.update({name: (byte_pos | uctypes.ARRAY , ln |  uctypes.UINT8)})
            byte_pos += ln


    def _make_struct(self):
        self.struct = uctypes.struct(uctypes.addressof(self.buf), self.layout, uctypes.LITTLE_ENDIAN)

    def _ld_buf(self):
        self.buf[:] = self.mem[self.memstart:self.memstart + self.span]

    def post_all(self):
        self.mem[self.memstart:self.memstart + self.span] = self.buf
        self._ld_buf()

    def toggle(self, key):
        self[key] = self[key] ^ 1


m = bytearray(64)

if __name__ == '__main__':
    nvam = ucMemReg('nvam', m,0,
                    ('id', 2, False, False),
                    ('flags', 1, False, False),
                    ('bit1', 1, True, None),
                    ('bit2', 1, True, None),
                    ('bit3', 1, True, None),
                    ('mode', 4, True, None),
                    ('value', 4, False, False),
                    ('name', 16, False, False))