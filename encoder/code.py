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
import neopixel

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)

pixel.brightness = 0.05
pixel.fill((255, 0, 0))

### Configure the pins and encoders here:

BAUD = 250000
NODE_SPECIFIC = False #True
NODE_SPECIFIC_MSGS = 0x6e0
NODE_ID = 0x90
DATA_ID = 0x300

encoder = [None] * 4
buttons = [None] * len(encoder)
switch =  [None] * len(encoder)
prevenc = [None] * len(encoder)
encval = [None] * len(encoder)
btnval = [None] * len(encoder)
change = [None] * int(len(encoder) / 2)
encoder[0] = rotaryio.IncrementalEncoder(board.D9,  board.D10, divisor=2 )
buttons[0] =      digitalio.DigitalInOut(board.D4)
encoder[1] = rotaryio.IncrementalEncoder(board.D11, board.D12, divisor=2 )
buttons[1] =      digitalio.DigitalInOut(board.D5)
encoder[2] = rotaryio.IncrementalEncoder(board.A0,  board.A1,  divisor=2 )
buttons[2] =      digitalio.DigitalInOut(board.D24)
encoder[3] = rotaryio.IncrementalEncoder(board.A2,  board.A3,  divisor=2 )
buttons[3] =      digitalio.DigitalInOut(board.D25)


for c, btn in enumerate(buttons):
    btn.direction = digitalio.Direction.INPUT
    btn.pull = digitalio.Pull.UP
    switch[c] = Debouncer(btn,interval=0.05)
    switch[c].update()
    btnval[c] = not switch[c].value

# getattr for usign config file?
# CAN setup
cs = DigitalInOut(board.CAN_CS)
cs.switch_to_output()
spi = board.SPI()

can_bus = CAN(
    spi, cs, loopback=False, silent=False, baudrate=BAUD
    )  # use loopback to test without another device


# Either the canid for the item as an owner
# or the sum of NODE_ID + NODE_SPECIFIC_MSGS

DATA_TYPE = "INT[2],BYTE"
DATA_MULTIPLIER = 1 #0.001



button_change = False

def return_data(data_type, data_code, multiplier, index, enc1, enc2, btn):
    valueData = canfix.utils.setValue(data_type,[enc1,enc2,[btn[0],btn[1],True,True,True,True,True,True]], multiplier)
    print(valueData)
    data = bytearray([])
    if NODE_SPECIFIC:
        data.append(data_code) # Control Code 12-19 index 1-8
        x = (index % 32) << 11 | DATA_ID
        data.append(x % 256)
        data.append(x >> 8)
    else:
        data.append(NODE_ID)
        data.append(index // 32)
        data.append(0x00)
    data.extend(valueData)
    return data
success = 0
count = 0
while True:
    time.sleep(0.1)
    pixel.brightness = 0
    for c, sw in enumerate(switch):
        sw.update()
        if sw.fell:
            btnval[c] = True
            change[ c // 2 ] = True
        if sw.rose:
            btnval[c] = False
            change[ c // 2 ] = True

    for c, enc in enumerate(encoder):
        encval[c] = enc.position
        if encval[c] > 2:
            encval[c] = int(encval[c] ** 1.8)
        elif encval[c] < -2:
            encval[c] = int(0 - (abs(encval[c]) ** 1.8))
        if encval[c] != 0 or prevenc[c] != 0:
            change[ c // 2 ] = True

    #if last_position is None or position != last_position:
    for c,ch in enumerate(change):
        #print(f"change: {c} count:{count}")

        if  ch or \
            count > 10:
            prevenc[ c * 2 ] = 0
            prevenc[ (c * 2 ) + 1 ] = 0

            change[ c ] = False
            encoder[ c * 2 ].position = 0
            encoder[ (c * 2 ) + 1 ].position = 0
        #baro = baro + position * 0.01

        # TODO Adjust index here
            if NODE_SPECIFIC:
                arbitration_id = NODE_ID + NODE_SPECIFIC_MSGS
            else:
                arbitration_id = DATA_ID
            index = c * 32 # 32 64 etc, total of 8 starting with 0
            code = (index // 32) + 0x0C
            print(f"Index: {index} Position1: {encval[c * 2]}, Position2: {encval[(c * 2) + 1]}")
            message = Message(id=arbitration_id, data=return_data(DATA_TYPE, code, DATA_MULTIPLIER, index, encval[c * 2],encval[(c * 2) + 1],[btnval[c * 2], btnval[(c * 2) + 1]]), extended=False)

            try:
                send_success = can_bus.send(message)
            except:
                pixel.fill((255, 0, 0))
                success = 0
                can_bus.restart()
            else:
                success += 1
                if success > 5:
                    pixel.fill((0, 255, 0))
            pixel.brightness = 0.05
    if count > 10:
        count = 0
    count += 1

