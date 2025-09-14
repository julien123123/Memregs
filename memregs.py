# class that manages memory, status and metadata in given memory
import struct, json

s_fl = 'cache.json'

class MemReg:
    __slots__ = ('name','_id','mem','buf','span','memstart','items','sv_cls')
    def __init__(self, name, mem, memstart, *args, span = 32):
        self.name = name
        self._id = hash(args + tuple([memstart, span]))
        self.mem = mem
        self.buf = mem[memstart:memstart + span]
        self.span = span
        self.memstart = memstart
        self.items = {}
        if not self._file_chk():
            self.items = {ar[0]: Memitem(i, *ar) for i, ar in enumerate(args)}
            self._order_items()
            self._ld_buf()
        self._sv_reg()

    def __str__(self):
        return '\n'.join(str(v) for v in self.items.values())

    def __getitem__(self, item):
        return self.items[item]

    def __setitem__(self, key, value):
        self.items[key].ch_val(value)
        
    def _file_chk(self):
        try:
            with open(s_fl, 'r') as f:
                if f.seek(0, 2):
                    f.seek(0)
                    l = json.load(f)
                    if self.name in l:
                        if l[self.name]['ID'] == self._id:
                            l[self.name].pop('ID')
                            self._load_reg(l[self.name])
                            return True
                self.sv_cls = True
                return False
        except OSError:
            self.sv_cls = True
            return False
        
    def _load_reg(self, dic):
        print('Retrieving from cache')
        self._ld_buf()
        for key, value in dic.items():
            self.items.update({key: Memitem.from_dict(value, self)})
            
        
    def _sv_reg(self):
        if hasattr(self, 'sv_cls') and self.sv_cls:
            print('Saving to cache')
            sv = {self.name: {k: {attr: val for attr, val in v.__dict__.items() if attr not in ('memref', 'buf')} for k, v in self.items.items()}}
            sv[self.name].update({'ID':self._id})
            try:
                with open(s_fl, 'w') as f:
                    if f.seek(0, 2):
                        f.seek(0)
                        l = json.load(f)
                        if self.name in l:
                            del l[self.name]
                    else:
                        l = {}
                    l.update(sv)
                    json.dump(l, f)
                    
            except OSError:
                print('fesse')

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
    def _ld_buf(self):
        self.buf[:] = self.mem[self.memstart:self.memstart + self.span]

    def post_all(self):
        for v in self.items.values():
            if v.bin:
                base_word = v.memref[0]
                mask = 1 << v.bit_pos
                new_w = base_word | mask if v.buf == 1 else base_word & ~mask
                v.memref[:] = struct.pack('B', new_w)
            else:
                if len(v.memref) != len(bytes(v.buf)):
                    v.buf = v.buf + b'\x00' * (len(v.memref) - len(v.buf))  # Adjust the length of v.buf
                v.memref[:] = bytes(v.buf)
        self.mem[self.memstart:self.memstart + self.span] = self.buf
        self._ld_buf()

class Memitem:
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
    #from microcontroller import nvm
    #import alarm
    import os
    '''
    nvmem = NVMem(nvm[0:32],('paw', 1, True), ('flag', 1, True), ('Nan', 4))
    print(nvmem)
    nvmem.items['flag'].ch_val(True)
    nvmem._ncode()
    '''
    b = bytearray(os.urandom(8))
    nvm = memoryview(b)
    nvam = MemReg('nvam', nvm, 0, ('REPL', 1, True), ('DATA', 1, True), ('MNT', 1, True), ('SAC', 3), ('PLUS', 4), span =8)
    #nvam.items['passw'].ch_val('Joli cil')
    #nvam.post_all()
    try:
        print(nvam)
    except TypeError:
        pass
    nvam['SAC'] = 'IOU'
    nvam.post_all()