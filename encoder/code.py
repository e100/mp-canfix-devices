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
NODE_ID = 0x90 #Unique ID for this device
DATA_ID = 0x300 #The canfix id for this data

encoder = [None] * 4
buttons = [None] * len(encoder)
switch =  [None] * len(encoder)
prevenc = [None] * len(encoder)
encval = [None] * len(encoder)
btnval = [None] * len(encoder)
change = [None] * int(len(encoder) / 2)
# Swap the encoder pins to reverse direction of encoder
# The divisor adjusts for pulses per click, see libary docs
encoder[0] = rotaryio.IncrementalEncoder(board.D24,  board.D25, divisor=4 )
buttons[0] =      digitalio.DigitalInOut(board.D4)
encoder[1] = rotaryio.IncrementalEncoder(board.TX , board.RX, divisor=4 )
buttons[1] =      digitalio.DigitalInOut(board.D6)
encoder[2] = rotaryio.IncrementalEncoder(board.A0,  board.A1,  divisor=4 )
buttons[2] =      digitalio.DigitalInOut(board.D9)
encoder[3] = rotaryio.IncrementalEncoder(board.A3,  board.A2,  divisor=4 )
buttons[3] =      digitalio.DigitalInOut(board.D5)


for c, btn in enumerate(buttons):
    btn.direction = digitalio.Direction.INPUT
    btn.pull = digitalio.Pull.UP
    switch[c] = Debouncer(btn,interval=0.05)
    switch[c].update()
    btnval[c] = not switch[c].value

# CAN setup
cs = DigitalInOut(board.CAN_CS)
cs.switch_to_output()
spi = board.SPI()

can_bus = CAN(
    spi, cs, loopback=False, silent=False, baudrate=BAUD
    )  # use loopback to test without another device


DATA_TYPE = "INT[2],BYTE"
DATA_MULTIPLIER = 1 #0.001



button_change = False

def return_data(data_type, data_code, multiplier, index, enc1, enc2, btn):
    # Send data for two encoders and their buttons
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
    # Wait 100ms
    time.sleep(0.1)
    # Turn the LED off
    pixel.brightness = 0
    for c, sw in enumerate(switch):
        # Check switch status
        sw.update()
        if sw.fell:
            # Flag button changed
            btnval[c] = True
            change[ c // 2 ] = True
        if sw.rose:
            # Flag vuttons changed
            btnval[c] = False
            change[ c // 2 ] = True

    for c, enc in enumerate(encoder):
        # Set value to steps changed
        encval[c] = enc.position
        # If steps chnaged is greater than 2 or less than -2 multiply the steps by 1.8
        # The faster your turn the encoder the large the number of steps output
        if encval[c] > 2:
            encval[c] = int(encval[c] ** 1.8)
        elif encval[c] < -2:
            encval[c] = int(0 - (abs(encval[c]) ** 1.8))
        if encval[c] != 0 or prevenc[c] != 0:
            # Flag encoder changed
            change[ c // 2 ] = True

    for c,ch in enumerate(change):
        # Every 10 loops send a message so data does not become old in the gateway
        # Send each loop if data has changed.
        if  ch or \
            count > 10:
            prevenc[ c * 2 ] = 0
            prevenc[ (c * 2 ) + 1 ] = 0
            # Reset change tracking
            change[ c ] = False
            encoder[ c * 2 ].position = 0
            encoder[ (c * 2 ) + 1 ].position = 0

            # Set the arbitration id
            if NODE_SPECIFIC:
                arbitration_id = NODE_ID + NODE_SPECIFIC_MSGS
            else:
                arbitration_id = DATA_ID
            index = c * 32 # 32 64 etc, total of 8 starting with 0
            code = (index // 32) + 0x0C
            print(f"Index: {index} Position1: {encval[c * 2]}, Position2: {encval[(c * 2) + 1]}")
            # Create the message to send
            message = Message(id=arbitration_id, data=return_data(DATA_TYPE, code, DATA_MULTIPLIER, index, encval[c * 2],encval[(c * 2) + 1],[btnval[c * 2], btnval[(c * 2) + 1]]), extended=False)

            try:
                # Send the message
                send_success = can_bus.send(message)
            except:
                # Set LED Red and restart the bus
                pixel.fill((255, 0, 0))
                success = 0
                can_bus.restart()
            else:
                success += 1
                if success > 5:
                    # set LED Green
                    # If the bus is diconnected it only errors once the buffer is full
                    # Waiting for five success prevents constant color changing
                    # because it only turns green if we can send more than it takes to fill the buffer 
                    pixel.fill((0, 255, 0))
            # Turn the LED on
            pixel.brightness = 0.05
    if count > 10:
        count = 0
    count += 1
