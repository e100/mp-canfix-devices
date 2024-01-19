# SPDX-FileCopyrightText: 2018 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT
import canfix.utils
import time
import rotaryio
import board
import digitalio
from adafruit_debouncer import Debouncer
from digitalio import DigitalInOut
from adafruit_mcp2515.canio import Message, RemoteTransmissionRequest
from adafruit_mcp2515 import MCP2515 as CAN


# Encoder/Switch setup
encoder1 = rotaryio.IncrementalEncoder(board.D9, board.D10, divisor=2, )
last_position1 = None
encoder2 = rotaryio.IncrementalEncoder(board.D11, board.D12, divisor=2, )
last_position2 = None

pin1 = digitalio.DigitalInOut(board.D4)
pin1.direction = digitalio.Direction.INPUT
pin1.pull = digitalio.Pull.UP
switch1 = Debouncer(pin1,interval=0.05)

pin2 = digitalio.DigitalInOut(board.D5)
pin2.direction = digitalio.Direction.INPUT
pin2.pull = digitalio.Pull.UP
switch2 = Debouncer(pin2,interval=0.05)

# getattr for usign config file?
# CAN setup
cs = DigitalInOut(board.CAN_CS)
cs.switch_to_output()
spi = board.SPI()

can_bus = CAN(
    spi, cs, loopback=False, silent=False, baudrate=250000
)  # use loopback to test without another device

NODE_SPECIFIC = False #True
NODE_SPECIFIC_MSGS = 0x6e0
NODE_ID = 0x90
DATA_ID = 0x300
# Either the canid for the item as an owner
# or the sum of NODE_ID + NODE_SPECIFIC_MSGS
if NODE_SPECIFIC:
    arbitration_id = NODE_ID + NODE_SPECIFIC_MSGS
else:
    arbitration_id = DATA_ID
DATA_TYPE = "INT[2],BYTE"
DATA_MULTIPLIER = 1 #0.001
DATA_INDEX = 0 # 32 64 etc, total of 8 starting with 0
DATA_CODE = (DATA_INDEX // 32) + 0x0C

switch1.update()
switch2.update()

button_change = False
buttons = [
not switch1.value, #This might not work well, we do not know initial state of the buttons
not switch2.value
]
def return_data(enc1,enc2,btn):
    valueData = canfix.utils.setValue(DATA_TYPE,[enc1,enc2,[btn[0],btn[1],True,True,True,True,True,True]], DATA_MULTIPLIER)
    print(valueData)
    data = bytearray([])
    if NODE_SPECIFIC:
        data.append(DATA_CODE) # Control Code 12-19 index 1-8
        x = (DATA_INDEX % 32) << 11 | DATA_ID
        data.append(x % 256)
        data.append(x >> 8)
    else:
        data.append(NODE_ID)
        data.append(DATA_INDEX // 32)
        data.append(0x00)
    data.extend(valueData)
    return data

count = 0
while True:
    time.sleep(0.1)
    switch1.update()
    switch2.update()

    position1 = encoder1.position
    position2 = encoder2.position

    if switch1.fell:
        #message = Message(id=arbitration_id, data=b"pressed", extended=True)
        buttons[0] = True
        button_change = True
        #send_success = can_bus.send(message)
        print("Send pressed success:", send_success)
    if switch1.rose:
        #message = Message(id=arbitration_id, data=b"released", extended=True)
        buttons[0] = False
        button_change = True
        #send_success = can_bus.send(message)
        print("Send released success:", send_success)
    if switch2.fell:
        buttons[1] = True
        button_change = True

    if switch2.rose:
        buttons[1] = False
        button_change = True


    #if last_position is None or position != last_position:
    if     (position1 != 0 or last_position1 != 0) \
        or (position2 != 0 or last_position2 != 0) \
        or count > 10 \
        or button_change:

        count = 0
        encoder1.position = 0
        encoder2.position = 0

        button_change = False
        #baro = baro + position * 0.01
        print(f"Position1: {position1}, Position2: {position2}")#, Sending BARO: {baro}")
        message = Message(id=arbitration_id, data=return_data(position1,position2,buttons), extended=False)
        #message = Message(id=0x1234ABCD, data=b"pressed", extended=True)
        try:
            send_success = can_bus.send(message)
        except:
            can_bus.restart()
        #print(f"Send pressed position: {position1}:", send_success)
    last_position1 = position1
    last_position2   = position2
    count += 1

