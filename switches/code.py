# SPDX-FileCopyrightText: 2018 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT
import board
import canfix.utils
from digitalio import DigitalInOut
from adafruit_mcp2515.canio import Message, RemoteTransmissionRequest
from adafruit_mcp2515 import MCP2515 as CAN
import neopixel
import time
import keypad

ROW_PINS = (
    board.A2,
    board.A3,
    board.D24,
    board.D25,
    board.RX,
    board.TX,

)
COLUMN_PINS = (
    board.A0,
    board.A1,
)

# Keys are addressed like, assuming 4 cols and 4 rows:
# 00, 01, 02, 03
# 04, 05, 06, 07
# 8,  9,  10, 11
# 12, 13, 14, 15

# Button State needs defined in multiples of 40. ie 40,80,120
# Each CAN message sends the data for 40 buttons
# So even if you have just 5 buttons, we still need to send the values for the other 35 bits
# Make sure you set button_state to a size large enough for all of your buttons
button_state = [False] * 40
# Do not change the next line:
index_changed = [False] * int(len(button_state) // 40)

# One shot buttons only send True one time
# Once True is sent, it will set the value back to False
# The user needs to release the button and press it again to send 
# the next True status for that button.
# To make a button one shot set the array index that matches the
# button number to True.
# False might be sent multiple times, but true is only ever sent once per press
# This is mostly used with pyEFIS 'simple' touchscreen buttons
# IF you want all buttons to be one shot, change False to True on the next line
OSB = [False] * len(button_state)
OSB[0] = True


BAUD = 250000
NODE_SPECIFIC = False #True
NODE_SPECIFIC_MSGS = 0x6e0
NODE_ID = 0x91
DATA_ID = 0x308

DATA_TYPE = "BYTE[5]"

keys = keypad.KeyMatrix(
            row_pins = ROW_PINS,
            column_pins = COLUMN_PINS,
            # Allow 50 msecs to debounce.
            interval=0.080, )
            
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)

pixel.brightness = 0.05
pixel.fill((255, 0, 0))

# CAN setup
cs = DigitalInOut(board.CAN_CS)
cs.switch_to_output()
spi = board.SPI()

can_bus = CAN(
    spi, cs, loopback=True, silent=True, baudrate=BAUD
    )  # use loopback to test without another device

def return_data(data_type, data_code, index, button_bits):
    valueData = canfix.utils.setValue(data_type,button_bits)
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

event = keypad.Event()
success = 0
count = 0
one_shot = -1
while True:
    time.sleep(0.1)
    pixel.brightness = 0
    if keys.events.get_into(event):
        print(event)
        if event.pressed:
            button_state[event.key_number] = True
            if OSB[event.key_number]:
                # This is a one show button
                one_shot = event.key_number
            # Flag to send this set of buttons
            index_changed[ ((event.key_number + 1) // 40) - 1 ] = True
        if event.released:
            button_state[event.key_number] = False
            # Flag to send this set of buttons
            index_changed[ ((event.key_number + 1) // 40) - 1 ] = True

    if NODE_SPECIFIC:
        arbitration_id = NODE_ID + NODE_SPECIFIC_MSGS
    else:
        arbitration_id = DATA_ID

    # How many messages do we need to send?
    messages = len(button_state)  // 40
    if messages == 0: messages = 1
    for idx in range(messages):
        #print(index_changed[idx])
        if not index_changed[idx]:
            continue
        index = idx * 32 # 32 64 etc, total of 8 starting with 0
        code = (index // 32) + 0x0C
        print(f"Index: {index} Buttons: {button_state[idx * 40: 40 * (idx + 1)]}")
        message = Message(id=arbitration_id, data=return_data(DATA_TYPE, code, index, button_state[idx * 40: 40 * (idx + 1)] ), extended=False)
        try:
            send_success = can_bus.send(message)
            # Reset flag for this set of buttons
            index_changed[idx] = False
            if one_shot > -1:
                print(one_shot)
                if one_shot < ((idx + 1) * 40):
                    # This message contained a one shot button that was true
                    # Wait a moment for the True to be processed
                    time.sleep(0.2)
                    # Set button back to False
                    button_state[one_shot] = False
                    # Reset the one_shot flag
                    one_shot = -1
                    
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

