import struct, json, uctypes
from functools import cache


#peut-être: sous-classes pour arguments en ordre de déclaration

class RegCache:
    """
    manages saving and loading of memory cache to a JSON file
    """
    def __init__(self, fnm):
        self.fnm = fnm
        self.cache = None

    def _ld(self):
        if self.cache is not None:
            return
        try:
            with open(self.fnm, 'r') as f:
                self.cache = json.load(f)
        except OSError:
            self.cache = {}

    def get(self, nm, h):
        self._ld()
        if nm in self.cache and self.cache[nm]['ID'] == h:
            r = self.cache[nm] #.copy()
            r.pop('ID', None)
            return r
        return False
    
    def push(self, name, value, id):
        self._ld()
        self.cache[name] = value.copy()
        self.cache[name]['ID'] = id
        with open(self.fnm, 'w') as f:
            json.dump(self.cache, f)

CACHE = RegCache('memcache.json')

def delcache():
    CACHE.cache = None

class Mem:
    """
    Base class for memory-mapped registers that manages a memory buffer.
    This avoids breaking micropython when modifying memory directly.
    """
    def __init__(self, name, mem, memstart, span):
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

class Struct(Mem):
    """
    This class dynamically creates and manages a memory-mapped structure using uctypes.struct.
    Structs can be fickle. Be sure that the memory area you give it is big enough otherwise it will crash micropython.
    """
    def __init__(self, name, mem, memstart, *args, span=32):
        super().__init__(name, mem, memstart, span)
        self._id = hash(args + tuple([memstart, span]))
        self.layout = {}
        sav =  CACHE.get(self.name, self._id)
        if not sav:
            self._parse_args(args)
            CACHE.push(self.name, self.layout, self._id)
        else:
            self.layout = sav
            for k, v in self.layout.items():
                if isinstance(v, list):
                    self.layout[k]= tuple(v) # because json saves tuples as lists and it creates problems with uctypes.layout
        self.struct = uctypes.struct(uctypes.addressof(self.buf), self.layout, uctypes.LITTLE_ENDIAN)

    def __getitem__(self, it):
        return getattr(self.struct, it)

    def __setitem__(self, key, value):
        if type(value) in (str, bytes, bytearray):
            value = value.encode('utf-8') if type(value) is str else value
            for i, b in enumerate(value):
                self[key][i] = b
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
            args = self._ngst(*args)
            if args[2]:
                binl.append(args)
            else:
                l.append(args)
        for dt in binl:
            name, ln, *rest = dt
            self.layout.update({name: byte_pos | bit_pos << uctypes.BF_POS | ln << uctypes.BF_LEN | uctypes.BFUINT8})
            bit_pos += ln
            if bit_pos >= 8:
                byte_pos += bit_pos // 8
                bit_pos = bit_pos % 8
        if bit_pos > 0:
            byte_pos += 1
            bit_pos = 0
        for dt in l:
            # name, length, bin, format
            if dt[3] == uctypes.ARRAY:
                self.layout.update({dt[0]: (byte_pos | dt[3], dt[1] | uctypes.UINT8)})
            else:
                print(dt)
                self.layout.update({dt[0]: (byte_pos | dt[3])})
            byte_pos += dt[1]

    @staticmethod
    def _ngst(name, span, *rst):
        lr = len(rst)
        bn = False
        fmt = False
        if lr == 2:
            bn, fmt = rst
        if lr == 1:
            if type(*rst) == bool:
                bn = rst[0]
            else:
                fmt = rst
        fmt = uctypes.UINT8 if not fmt else getattr(uctypes, fmt)
        return name, span, bn, fmt

    def toggle(self, key):
        self[key] = self[key] ^ 1

        
class Pack(Mem):
    """
    Pythonic class that manages memory-mapped registers with individual items.
    Can be a better choice when uctypes.struct is too rigid.
    """
    def __init__(self, name, mem, memstart, *args, span = 32):
        super().__init__(name, mem, memstart, span)
        self._id = hash(args + tuple([memstart, span]))
        self.items = {}
        self.sav = self._from_cache()
        if self.sav:
            self.items = {ar[0]: Memitem(i, *ar) for i, ar in enumerate(args)}
            self._order_items()
            CACHE.push(self.name, {k: {attr: val for attr, val in v.__dict__.items() if attr not in ('memref', 'buf')} for k, v in self.items.items()}, self._id)

    def __str__(self):
        return '\n'.join(str(v) for v in self.items.values())

    def __getitem__(self, item):
        return self.items[item]

    def __setitem__(self, key, value):
        self.items[key].ch_val(value)
    
    def _from_cache(self):
        r = CACHE.get(self.name, self._id)
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
            self.buf = new_val & 1
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
    nvam = Pack('nvam', nvm, 0, ('REPL', 1, True), ('DATA', 1, True), ('MNT', 1, True), ('SAC', 3), ('PLUS', 4), span =8)
    mimi = Pack('mimi', nvm, 8, ('passw', 1), ('flag', 1, True), ('Nan', 4))
    nvam['SAC'] = 'IOU'
    nvam.post_all()
    try:
        print(nvam)
    except TypeError:
        pass

    print(mimi)
    m = bytearray(64)
    nvim = Struct('nvim', m, 0,
                  ('id', 2, False, False),
                  ('flags', 1, False, False),
                  ('bit1', 1, True, None),
                  ('bit2', 1, True, None),
                  ('bit3', 1, True, None),
                  ('mode', 4, True, None),
                  ('value', 4, False, False),
                  ('name', 16, False, 'ARRAY'))
    
    nvim['name'] = 'Julien'
    nvim['value'] = 42
    nvim.post_all()
    print(nvim)