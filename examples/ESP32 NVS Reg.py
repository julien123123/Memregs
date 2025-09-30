import memregs, esp32, time, sys

class NVSreg(memregs.Struct):
    """ This class interfaces with memregs and ESP32's NVS memory"""
    nvs = esp32.NVS('reg')

    def post_all(self):
        NVSreg.nvs.set_blob(self.name, self.buf)
        NVSreg.nvs.commit()
        self.ld_buf()

    def ld_buf(self):
        try:
            NVSreg.nvs.get_blob(self.name, self.buf)
        except OSError:
            # If the memory doesn't already exist return an empty buf
            self.buf = bytearray([0x00]*self.span)

config = NVSreg('config', bytearray(32), 0, ('favorite color', 10, 'ARRAY'), ('LANGUAGE', 2, 'ARRAY'),
                ('INIT_DATE', 1, 'UINT32'), ('PLATFORM', 6, 'ARRAY'), ('INITED', 1, True))
if not config['INITED']:
    print("Writting config")
    config['favorite color'] = input("Type your favourite coulour:")
    config['LANGUAGE'] = input("Your first language in 2 letters:")
    config['INIT_DATE'] = time.time()
    config['PLATFORM'] = sys.platform
    config.toggle('INITED')
    config.post_all()
    print("Config Saved")
else:
    print(f"Inited on: {time.localtime(config['INIT_DATE'])}\nCurrent platform: {config['PLATFORM'].decode().strip("\x00")}"
          f"\nFavourite color is {config['favorite color'].decode().strip("\x00")}\nFirst language: {config['LANGUAGE'].decode()}")
