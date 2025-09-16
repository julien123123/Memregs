# class that manages memory, status and metadata in given memory
import struct, json, uctypes

class MemCache:
    """
    Class to manage saving and loading of memory cache to a JSON file
    """
    def __init__(self, fnm):
        self.fnm = fnm
        self.cache = {}
        self.h = False  

    def _ld(self):
        try:
            with open(self.fnm, 'r') as f:
                if f.seek(0, 2):
                    f.seek(0)
                    print('Loadind from cache...')
                    self.cache = json.load(f)
                    self.h = hash(str(self.cache))
                    return
        except OSError:
            pass
        self.cache = {}
        self.h = hash(str(self.cache))

    def get(self, nm, h):
        self._ld() if not self.h else None
        if nm in self.cache.keys():
            if self.cache[nm]['ID'] == h:
                self.cache[nm].pop('ID')
                r = self.cache[nm]
                del self.cache[nm]
                return r
            del self.cache[nm]
        return False
    
    def push(self, name, value, id):
        l = {}
        v_cp = value.copy() # Otherwise this crashes the ESP32 because it's added in struct.layout
        v_cp.update({'ID': id})
        try:
            with open(self.fnm, 'r') as f:
                if f.seek(0, 2):
                    f.seek(0)
                    l = json.load(f)
                    if name in l:
                        del l[name]
        except OSError:
            pass

        l.update({name:v_cp})
        
        print(f'Saving {name} to cache....')
        with open(self.fnm, 'w') as f:
                json.dump(l, f)

        if name in self.cache.keys():
            del self.cache[name]

'''
args structure: (name, length, bin=False, uctype format = None)
'''
class Reg:
    """
    Base class for memory-mapped registers that manages a memory buffer.
    This avoids breaking micropython when modifying memory directly.
    """
    c = False
    def __init__(self, name, mem, memstart, span):
        self._id = False
        self.name = name
        self.mem = mem
        self.memstart = memstart
        self.span = span
        self.buf = mem[memstart:memstart + span]

    def post_all(self):
        self.mem[self.memstart:self.memstart + self.span] = self.buf
        self.ld_buf()
    
    def ld_buf(self):
        self.buf[:] = self.mem[self.memstart:self.memstart + self.span]

class ucMemReg(Reg):
    c = MemCache('ccache.json')
    def __init__(self, name, mem, memstart, *args, span=32):
        super().__init__(name, mem, memstart, span)
        
        self._id = hash(args + tuple([memstart, span]))
        self.struct = {}
        self.layout = {}
        self.sav = self._from_cache()
        if self.sav:
            self._parse_args(args)
            ucMemReg.c.push(self.name, self.layout, self._id)
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

    def _from_cache(self):
        r = ucMemReg.c.get(self.name, self._id)
        if r:
            self.layout = r
            for k, v in self.layout.items():
                if type(v) is list:
                    self.layout[k] = tuple(v) # because json saves tuples as lists, and uctypes needs tuples
            return False
        return True

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
    
    @staticmethod
    def pack_code(c):
        # map struct format characters to uctypes types, not sure if it's the way I want it to go.
        codes = b"bBhHiIlLqQfd?"
        types = [uctypes.INT8, uctypes.UINT8, uctypes.INT16, uctypes.UINT16, uctypes.INT32, uctypes.UINT32, uctypes.INT32, uctypes.UINT32, uctypes.INT64, uctypes.UINT64, uctypes.FLOAT32, uctypes.FLOAT64, uctypes.UINT8]
        try:
            return types[codes.index(c.encode())]
        except ValueError:
            raise ValueError(f"Unsupported struct format: {c}")

    def _make_struct(self):
        self.struct = uctypes.struct(uctypes.addressof(self.buf), self.layout, uctypes.LITTLE_ENDIAN)

    def toggle(self, key):
        self[key] = self[key] ^ 1

        
class MemReg(Reg):
    c = MemCache('cache.json')

    def __init__(self, name, mem, memstart, *args, span = 32):
        super().__init__(name, mem, memstart, span)
        self._id = hash(args + tuple([memstart, span]))
        self.items = {}
        self.sav = self._from_cache()
        if self.sav:
            self.items = {ar[0]: Memitem(i, *ar) for i, ar in enumerate(args)}
            self._order_items()
            MemReg.c.push(self.name, {k: {attr: val for attr, val in v.__dict__.items() if attr not in ('memref', 'buf')} for k, v in self.items.items()}, self._id)

    def __str__(self):
        return '\n'.join(str(v) for v in self.items.values())

    def __getitem__(self, item):
        return self.items[item]

    def __setitem__(self, key, value):
        self.items[key].ch_val(value)
    
    def _from_cache(self):
        r = MemReg.c.get(self.name, self._id)
        if r:
            for key, value in r.items():
                self.items.update({key: Memitem.from_dict(value, self)})
            return False
        return True

    def _order_items(self):
        """
            This function ensures that all items stay in the same order every time
            It also makes it very easy to combine bits with bytes
        """
        word_cursor, bit_cursor = 0, 0

        # Process binary items first
        for itm in sorted((i for i in self.items.values() if i.bin), key=lambda obj: obj.indx):
            if bit_cursor >= 8:
                word_cursor += 1
                bit_cursor %= 8
            itm.byte_pos = word_cursor
            itm.bit_pos = bit_cursor
            itm.mask = 1 << bit_cursor
            bit_cursor += itm.length
            itm.memref = memoryview(self.buf)[itm.byte_pos:itm.byte_pos + 1]
            itm.buf = itm.raw_val

        # If bits are not aligned, move to next byte
        if bit_cursor > 0:
            word_cursor += 1
            bit_cursor = 0

        # Process non-binary items
        for itm in sorted((i for i in self.items.values() if not i.bin), key=lambda obj: obj.indx):
            itm.byte_pos = word_cursor
            word_cursor += itm.length
            itm.memref = memoryview(self.buf)[itm.byte_pos:itm.byte_pos + itm.length]
            itm.buf = itm.raw_val

    def post_all(self):
        for v in self.items.values():
            if v.bin:
                base_word = v.memref[0]
                new_w = base_word | v.mask if v.buf == 1 else base_word & ~v.mask
                v.memref[:] = struct.pack('B', new_w)
            else:
                if len(v.memref) != len(bytes(v.buf)):
                    v.buf = v.buf + b'\x00' * (len(v.memref) - len(v.buf))  # Adjust the length of v.buf
                v.memref[:] = bytes(v.buf)
        super().post_all()

class Memitem:
    __slots__ = ('indx','name','length','bin','pack_format','bit_pos','byte_pos','memref','buf','mask')
    @classmethod
    def from_dict(cls,d, reg):
        obj = cls(d['indx'], d['name'], d['length'], d.get('bin', False), d.get('pack_format', False))
        obj.bit_pos = d['bit_pos']
        obj.byte_pos = d['byte_pos']
        obj.memref = memoryview(reg.buf)[obj.byte_pos:obj.byte_pos + (1 if obj.bin else obj.length)]
        obj.buf = obj.raw_val
        return obj
        
    def __init__(self,indx, name, lenght, bin = False, pack_format=False):
        self.indx = indx
        self.name = name
        if lenght <= 0:
            raise ValueError('item length must be greater than 0')
        self.length = lenght
        self.bin = bin
        self.pack_format = pack_format

        ### Variables that will be set by Memreg._order_items()
        self.bit_pos = 0
        self.byte_pos = 0
        self.memref = None
        self.mask = 0
        self.buf = 0 # Set to raw_val in Memreg

    @property
    def value(self): # parsing values here makes it less expensive to call
        return struct.unpack(self.pack_format, bytes(self.memref))[0] if self.pack_format else bytes(self.memref) if not self.bin else bytes(self.memref)[0] >> self.bit_pos & 1

    @property
    def raw_val(self):
        return bytes(self.memref) if not self.bin else bytes(self.memref)[0] >> self.bit_pos & 1

    def __str__(self):
        return f'{self.name}: \n\t index = {self.indx}\n\t val ={self.value}\n\t byte_pos = {self.byte_pos}\n\t bin ={self.bin}\n\t bit_pos = {self.bit_pos}'

    def reset(self):
        self.buf = bytearray([0x00] * self.length) if not self.bin else 0

    def ch_val(self, new_val):
        self.reset()
        if self.bin:
            if (len(bin(new_val))-2) > self.length:
                raise ValueError('nb of bits superior to "lenght" attribute')
            self.buf = new_val
        elif self.pack_format:
            self.buf = struct.pack(self.pack_format, new_val)
        else:
            if isinstance(new_val, (bytes, bytearray)):
                self.buf = new_val
            if isinstance(new_val, (str, int)):
                self.buf = str(new_val).encode()

    def toggle(self):
        if not self.bin:
            raise AttributeError('item is not defined as binary, cannot toggle!')
        if self.length >1:
            raise ValueError("item's length is superior to 1, cannot toggle")
        self.buf = (self.raw_val + 1) % 2

if __name__ == "__main__":
    import os
    
    b = bytearray(os.urandom(16))
    nvm = memoryview(b)
    nvam = MemReg('nvam', nvm, 0, ('REPL', 1, True), ('DATA', 1, True), ('MNT', 1, True), ('SAC', 3), ('PLUS', 4), span =8)
    mimi = MemReg('mimi', nvm, 8, ('passw', 1), ('flag', 1, True), ('Nan', 4))
    nvam['SAC'] = 'IOU'
    nvam.post_all()
    try:
        print(nvam)
    except TypeError:
        pass

    print(mimi)
    
    m = bytearray(64)
    nvim = ucMemReg('nvim', m,0,
                    ('id', 2, False, False),
                    ('flags', 1, False, False),
                    ('bit1', 1, True, None),
                    ('bit2', 1, True, None),
                    ('bit3', 1, True, None),
                    ('mode', 4, True, None),
                    ('value', 4, False, False),
                    ('name', 16, False, False))
    
    nvim['name'] = 'Julien'
    nvim['value'] = 42
    nvim.post_all()
    print(nvim)