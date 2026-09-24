import pyvisa

rm = pyvisa.ResourceManager('@py')  # or pyvisa.ResourceManager() if using Keysight IO
print(rm.list_resources())
