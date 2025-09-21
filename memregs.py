import struct, json, uctypes, binascii

#peut-être: sous-classes pour arguments en ordre de déclaration

cache_f = 'memcache.json'
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
            r = self.cache[nm].copy()
            r.pop('ID', None)
            return r
        return False
    
    def push(self, name, value, id):
        self._ld()
        self.cache[name] = value.copy()
        self.cache[name]['ID'] = id
        with open(self.fnm, 'w') as f:
            json.dump(self.cache, f)

CACHE = RegCache(cache_f)

def clear_cache():
    CACHE.cache = None
    
def delete_cache():
    import os
    os.remove(cache_f)

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
        # Dans le fond, c'est juste bon pour struct
        # Pour pack, chaque item écrit dans mem directement
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
        sav = CACHE.get(self.name, self._id)
        if not sav:
            self.items = {ar[0]: Memitem(i, *ar) for i, ar in enumerate(args)}
            self._order_items()
            CACHE.push(self.name, {
                k: {attr: (binascii.hexlify(val) if attr == "inreg" else val) for attr, val in v.__dict__.items() if
                    attr not in ("memref", "buf")} for k, v in self.items.items()}, self._id)
        else:
            for k, d in sav.items():
                self.items[k] = Memitem.from_dict(d, self)

    def __str__(self):
        return '\n'.join(str(v) for v in self.items.values())

    def __getitem__(self, k):return self.items[k]
    def __setitem__(self, k, v): self.items[k].ch_val(v)

    def _order_items(self):
        """
            This function ensures that all items stay in the same order every time
            It also makes it very easy to combine bits with bytes
        """
        word_cursor, bit_cursor = 0, 0
        # Process binary items first
        for itm in sorted((i for i in self.items.values() if i.inreg[0] & (1 <<7)), key=lambda obj: obj.indx):
            if bit_cursor >= 8:
                word_cursor += 1
                bit_cursor %= 8
            itm.inreg[3] = word_cursor
            itm.inreg[0] |= bit_cursor & ((1 << 6)-1)
            itm.mask = 1 << bit_cursor
            bit_cursor += itm.inreg[2]
            itm.memref = memoryview(self.buf)[itm.inreg[3]:itm.inreg[3] + 1]
            itm.buf = itm.raw_val
        # If bits are not aligned, move to next byte
        if bit_cursor > 0:
            word_cursor += 1
            bit_cursor = 0
        # Process non-binary items
        for itm in sorted((i for i in self.items.values() if not i.inreg[0] & (1<<7)), key=lambda obj: obj.indx):
            itm.inreg[3] = word_cursor
            word_cursor += (2**(itm.inreg[0]>>5)&0b11)*itm.inreg[2]
            itm.memref = memoryview(self.buf)[itm.inreg[3]:itm.inreg[3] + itm.inreg[2]*(1 <<((itm.inreg[0] >>5)&0b11))]
            itm.buf = itm.raw_val

    def post_all(self):
        for v in self.items.values():
            if v.inreg[0] & 1 << 7 :
                base_word = v.memref[0]
                new_w = base_word | v.mask if v.buf == 1 else base_word & ~v.mask
                v.memref[:] = struct.pack('B', new_w)
            else:
                if len(v.memref) != len(bytes(v.buf)):
                    v.buf = v.buf + b'\x00' * (len(v.memref) - len(v.buf))  # Adjust the length of v.buf
                v.memref[:] = bytes(v.buf)
        super().post_all()

class Memitem:
    #TODO: this class doesn't neet to have a buffer, it can write directly to memref, or pack_into
    #post all can alost just be the method in Mem
    # BITPOS  = 5 BITS : inreg[0], bit 0-4
    # BIN = 1 BIT : inreg[0], bit 7
    # PACKFMT =  8 BITS: inreg[1]
    # Packmultiplier = 2 Bits : inreg[0], bit 5, 6
    # LENGTH = 8 BITS : inreg[2]
    # BYTEPOS = 8 BITS : inreg[3]

    __slots__ = ('indx','name','length','bin','pack_format','memref','buf','mask', 'inreg')
    @classmethod
    def from_dict(cls,d, reg):
        obj = cls(d['indx'], d['name'], 0, inreg=d['inreg'])
        obj.length = obj.inreg[2]
        obj.memref = memoryview(reg.buf)[obj.inreg[3]:obj.inreg[3] + (1 if (obj.inreg[0] & (1<<7)) else obj.inreg[2]*2**((obj.inreg[0]>>5)&0b11))]
        obj.buf = obj.raw_val
        return obj

    def __init__(self,indx, name, lenght, bin = False, pack_format=False, inreg= None):
        self.indx = indx
        self.name = name
        if not inreg:
            self.inreg = bytearray(4)
            if bin:
                self.inreg[0] |= 1 << 7
            if pack_format:
                self.inreg[1] = ord(pack_format)
            else:
                self.inreg[1] = ord('B')
            try:
                self.inreg[0] |= ((len(struct.pack(chr(self.inreg[1]), 0)) >> 1) & 3) << 5
            except TypeError:
                self.inreg[0] |= ((len(struct.pack(chr(self.inreg[1]), 'B')) >> 1) & 3) << 5

            self.inreg[2] = lenght
        else:
            self.inreg = binascii.unhexlify(inreg)
        self.memref = None
        self.mask = 0
        self.buf = 0 # Set to raw_val in Memreg

    @property
    def value(self): # parsing values here makes it less expensive to call
        return struct.unpack(chr(self.inreg[1]), bytes(self.memref))[0] if self.inreg != ord('B') else bytes(self.memref) if not self.bin else bytes(self.memref)[0] >> self.bit_pos & 1

    @property
    def raw_val(self):
        return bytes(self.memref) if not self.inreg[0] & (1<<7) else (bytes(self.memref)[0] >> (self.inreg[0] & 0b11111)) & 1

    def __str__(self):
        return f'{self.name}: \n\t index = {self.indx}\n\t val ={self.value}\n\t byte_pos = {self.inreg[3]}\n\t bin = {bool(self.inreg[0] >> 7)}\n\t bit_pos = {self.inreg[0]&0b11111}'

    def reset(self):
        self.buf = bytearray([0x00] * 2**((self.inreg[0]>>5) & 0b11)*self.inreg[2]) if not self.inreg[0] & (1<<7) else 0

    def ch_val(self, new_val):
        self.reset()
        if self.inreg[0] & (1<<7):
            self.buf = new_val & ((1 << self.inreg[1])-1)
        elif isinstance(new_val, (bytes, bytearray)):
            self.buf[:] = new_val
        elif isinstance(new_val, (str)):
            self.buf[:] = str(new_val).encode()
        elif self.inreg[1] != ord('B'):
            self.buf[:] = struct.pack(chr(self.inreg[1])*self.inreg[2], new_val)

    def toggle(self):
        if not (self.inreg[0] >> 7) & 1:
            raise AttributeError('item is not defined as binary, cannot toggle!')
        if self.inreg[2] >1:
            raise ValueError("item's length is superior to 1, cannot toggle")
        self.buf = self.raw_val ^ 1

if __name__ == "__main__":
    import os
    
    b = bytearray(os.urandom(32))
    nvm = memoryview(b)
    nvam = Pack('nvam', nvm, 0, ('REPL', 1, True), ('DATA', 1, True), ('MNT', 1, True), ('SAC', 3), ('PLUS', 4), span =8)
    mimi = Pack('mimi', nvm, 8, ('passw', 10), ('flag', 1, True), ('Nan', 4))
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