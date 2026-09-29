import pyvisa

rm = pyvisa.ResourceManager('@py')  # or pyvisa.ResourceManager() if using Keysight IO
#rm = pyvisa.ResourceManager()
print("Printing list resources")
print(rm.list_resources())
