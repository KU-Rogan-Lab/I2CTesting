import pyvisa

# Initialize resource manager
rm = pyvisa.ResourceManager('@py')

# Replace with your actual instrument VISA address found from list_resources()
visa_address = 'USB0::0x0957::0x3F07::MYXXXXXXXX::0::INSTR'

try:
  # Open connection to power supply
  psu = rm.open_resource(visa_address)
  psu.timeout = 5000  # Set timeout in milliseconds

  # Query identification
  print('Connected to:', psu.query('*IDN?').strip())

  # Select channel (e.g., Channel 1)
  channel = '(@1)'

  # Read actual measured voltage and current
  voltage = float(psu.query(f'MEASure:VOLTage? {channel}'))
  current = float(psu.query(f'MEASure:CURRent? {channel}'))

  print(f'Channel 1 - Voltage: {voltage:.4f} V')
  print(f'Channel 1 - Current: {current:.4f} A')

  psu.close()

except Exception as e:
  print('Error communicating with the instrument:', e)
