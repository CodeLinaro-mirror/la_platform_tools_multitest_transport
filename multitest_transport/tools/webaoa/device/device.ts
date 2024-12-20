/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/** Google vendor ID. */
export const GOOGLE_VID = 0x18D1;
/** Accessory mode product IDs. */
export const AOA_PID = [0x2D00, 0x2D01, 0x2D02, 0x2D03, 0x2D04, 0x2D05];
/** Accessory mode with ADB product IDs. */
export const ADB_PID = [0x2D01, 0x2D03, 0x2D05];
/** Accessory mode with AUDIO product IDs. */
export const AUDIO_PID = [0x2D02, 0x2D03, 0x2D04, 0x2D05];

// Simulated accessory information
const MANUFACTURER = new TextEncoder().encode('Android\0');
const MODEL = new TextEncoder().encode('WebAOA\0');
const VERSION = new TextEncoder().encode('1.0\0');

/** AOA USB requests. */
export enum AoaRequest {
  GET_PROTOCOL = 51,         // Check protocol support
  SEND_STRING = 52,          // Send accessory information
  START = 53,                // Restart in accessory mode
  REGISTER_HID = 54,         // Register a HID
  UNREGISTER_HID = 55,       // Unregister a HID
  SET_HID_REPORT_DESC = 56,  // Send the HID descriptor
  SEND_HID_EVENT = 57,       // Send a HID event
  SET_AUDIO_MODE = 58,       // Enable audio mode
}

const CONFIG_DELAY_MILLIS = 300;    // Delay after configuration change
const POLL_INTERVAL_MILLIS = 500;   // Delay after looking for a device
const OPEN_TIMEOUT_MILLIS = 2500;   // Default timeout when opening connection
const RESET_TIMEOUT_MILLIS = 5000;  // Default timeout when resetting connection
const EVENT_DELAY_MILLIS = 10;      // Delay between sending HID events

/** Touch screen motion types. */
export enum TouchType {
  UP = 0b00,    // Lift finger away from screen to finish a gesture
  DOWN = 0b11,  // Touch the screen to start or continue a gesture
}

/** System button actions. */
export enum SystemButton {
  WAKE = 0b001,  // System wake button
  HOME = 0b010,  // Home button
  BACK = 0b100,  // Back button
}

/** Thrown if an AOA operation fails. */
export class AoaError extends Error {
  constructor(message: string, readonly device?: AoaDevice) {
    super(message);
  }
}

/**
 * Checks whether a {@link USBDevice} supports the AOAv2 protocol.
 * @param device opened USB device to check
 */
async function isCompatible(device: USBDevice): Promise<boolean> {
  try {
    const result = await device.controlTransferIn(
        {
          requestType: 'vendor',
          recipient: 'device',
          request: AoaRequest.GET_PROTOCOL,
          value: 0,
          index: 0
        },
        2);
    // if successful, the data will contain the supported protocol version
    return result.status === 'ok' && result.data!.getInt8(0) >= 2;
  } catch {
    return false;
  }
}

/**
 * USB-connected Android device which supports the AOAv2 protocol. Uses WebUSB
 * to perform gestures on the touchscreen, press a combination of keys, or press
 * system buttons (e.g. power, home, back).
 *
 * @see https://source.android.com/devices/accessories/aoa2
 * @see https://wicg.github.io/webusb
 */
export class AoaDevice {
  /** device serial number */
  readonly serialNumber: string;

  /** @param delegate compatible {@link USBDevice} with a valid serial number */
  private constructor(private delegate: USBDevice) {
    // cache serial number to use when reconnecting
    this.serialNumber = delegate.serialNumber as string;
  }

  /**
   * Factory method which converts a {@link USBDevice} to an {@link AoaDevice}
   * if it is compatible with the AOAv2 protocol.
   * @param device USB device to use
   * @return AOA device
   */
  static async fromUSBDevice(device: USBDevice): Promise<AoaDevice> {
    if (!device.serialNumber) {
      throw new AoaError('Missing serial number');
    }
    // open connection if necessary, and check for AOAv2 compatibility
    const opened = device.opened;
    await device.open();
    if (await isCompatible(device)) {
      return new AoaDevice(device);
    }
    // device is incompatible, close connection if it was initially closed
    if (!opened) {
      await device.close();
    }
    throw new AoaError(`Device ${device.serialNumber} is not AOAv2-compatible`);
  }

  /** @return device's vendor ID */
  get vendorId(): number {
    return this.delegate.vendorId;
  }

  /** @return device's product ID */
  get productId(): number {
    return this.delegate.productId;
  }

  /** @return device's manufacturer name */
  get manufacturerName(): string|undefined {
    return this.delegate.manufacturerName;
  }

  /** @return device's product name */
  get productName(): string|undefined {
    return this.delegate.productName;
  }

  /** @return true if the USB device connection is open */
  isConnected(): boolean {
    return this.delegate.opened;
  }

  /** @return true if the device is currently in accessory mode */
  isAccessoryMode(): boolean {
    return GOOGLE_VID === this.vendorId && AOA_PID.includes(this.productId);
  }

  /** @return true if the device has USB debugging enabled */
  isAdbEnabled(): boolean {
    return GOOGLE_VID === this.vendorId && ADB_PID.includes(this.productId);
  }

  /** @return true if the device has audio enabled */
  isAudioEnabled(): boolean {
    return GOOGLE_VID === this.vendorId && AUDIO_PID.includes(this.productId);
  }

  /**
   * Perform an outgoing (towards device) USB control transfer.
   * @param request packet request field
   * @param value packet value field
   * @param index packet index field
   * @param data output data buffer
   * @throws AoaError if the transfer fails
   */
  private async transfer(
      request: AoaRequest, value: number, index: number,
      data?: Uint8Array): Promise<void> {
    const result = await this.delegate.controlTransferOut(
        {requestType: 'vendor', recipient: 'device', request, value, index},
        data);
    if (result.status !== 'ok') {
      throw new AoaError(
          `Transfer failed with status '${result.status}'`, this);
    }
  }

  /**
   * Reconnects to the USB device.
   * @param timeout max milliseconds to wait for device
   * @throws AoaError if the device connection was lost
   */
  private async reconnect(timeout: number): Promise<void> {
    const start = Date.now();
    for (let time = 0; time <= timeout; time = Date.now() - start) {
      // find device using its serial number
      const devices = await navigator.usb.getDevices();
      const device = devices.find(d => d.serialNumber === this.serialNumber);
      if (device && await isCompatible(device)) {
        this.delegate = device;  // device was found and is valid
        return;
      }
      await this.sleep(POLL_INTERVAL_MILLIS);  // check again periodically
    }
    throw new AoaError(
        `Device ${this.serialNumber} unpaired or disconnected`, this);
  }

  /**
   * Waits for a specified number of milliseconds.
   * @param millis milliseconds to wait
   */
  async sleep(millis: number): Promise<void> {
    await new Promise(resolve => {
      setTimeout(resolve, millis);
    });
  }

  /**
   * Connects to the device and prepares it.
   * @param timeout max milliseconds to wait for the device
   * @throws AoaError if the device connection was lost
   */
  async open(timeout = OPEN_TIMEOUT_MILLIS): Promise<void> {
    await this.delegate.open();
    if (!this.isAccessoryMode()) {
      // device is not currently in accessory mode, send accessory information,
      // and reconnect in accessory mode
      await this.transfer(AoaRequest.SEND_STRING, 0, 0, MANUFACTURER);
      await this.transfer(AoaRequest.SEND_STRING, 0, 1, MODEL);
      await this.transfer(AoaRequest.SEND_STRING, 0, 3, VERSION);
      await this.transfer(AoaRequest.SET_AUDIO_MODE, 1, 0);
      await this.transfer(AoaRequest.START, 0, 0);
      await this.sleep(CONFIG_DELAY_MILLIS);
      await this.reconnect(timeout);
    }
    await Promise.all(HID.VALUES.map(hid => this.registerHID(hid)));
    await this.sleep(CONFIG_DELAY_MILLIS);
  }

  /** Register a human interface device. */
  private async registerHID(hid: HID): Promise<void> {
    await this.transfer(AoaRequest.REGISTER_HID, hid.id, hid.data.length);
    await this.transfer(AoaRequest.SET_HID_REPORT_DESC, hid.id, 0, hid.data);
  }

  /** Unregisters HIDs and closes connection. */
  async close(): Promise<void> {
    if (this.delegate.opened) {
      if (this.isAccessoryMode()) {
        await Promise.all(HID.VALUES.map(hid => this.unregisterHID(hid)));
      }
      await this.delegate.close();
    }
  }

  /** Unregisters a human interface device. */
  private async unregisterHID(hid: HID): Promise<void> {
    await this.transfer(AoaRequest.UNREGISTER_HID, hid.id, 0);
  }

  /**
   * Closes and re-opens the connection.
   * @param timeout max milliseconds to wait for the device
   * @throws AoaError if the device connection was lost
   */
  async reset(timeout = RESET_TIMEOUT_MILLIS): Promise<void> {
    await this.close();
    await this.reconnect(timeout);
    await this.open();
  }

  /**
   * Send a HID event (touch, keystroke, etc.) to the device.
   * @param hid interface descriptor
   * @param data event data
   */
  private async sendHidEvent(hid: HID, data: Uint8Array): Promise<void> {
    await this.transfer(AoaRequest.SEND_HID_EVENT, hid.id, 0, data);
  }

  /** Clicks on a point. */
  async click(point: Point): Promise<void> {
    await this.touch(TouchType.DOWN, point);
    await this.sleep(EVENT_DELAY_MILLIS);
    await this.touch(TouchType.UP, point);
  }

  /**
   * Swipe from one position to another in the specified duration.
   * @param from starting position
   * @param to final position
   * @param millis swipe motion duration in milliseconds
   */
  async swipe(from: Point, to: Point, millis: number) {
    const start = Date.now();
    for (let dt = 0; dt <= millis; dt = Date.now() - start) {
      const progress = dt / Math.max(millis, 1);
      const point = new Point(
          progress * to.x + (1 - progress) * from.x,
          progress * to.y + (1 - progress) * from.y);
      await this.touch(TouchType.DOWN, point);
      await this.sleep(EVENT_DELAY_MILLIS);
    }
    await this.touch(TouchType.UP, to);
  }

  /** Send a touch event to the device. */
  private async touch(type: TouchType, point: Point): Promise<void> {
    const x = point.x;
    const y = point.y;
    const data = new Uint8Array([type, x, x >> 8, y, y >> 8]);
    await this.sendHidEvent(HID.TOUCH_SCREEN, data);
  }

  /**
   * Press a combination of keys.
   * @param keys list of keys to press
   */
  async pressKeys(keys: Key[]) {
    for (const key of keys) {
      const modifier = key.modifiers.reduce((a, b) => a | b, 0);
      await this.sendHidEvent(
          HID.KEYBOARD, new Uint8Array([modifier, key.usage]));
      await this.sleep(EVENT_DELAY_MILLIS);
      await this.sendHidEvent(HID.KEYBOARD, new Uint8Array([0, 0]));
      await this.sleep(EVENT_DELAY_MILLIS);
    }
  }

  /** Press the device's back button. */
  async goBack(): Promise<void> {
    await this.sendHidEvent(HID.SYSTEM, new Uint8Array([SystemButton.BACK]));
  }

  /** Press the device's home button. */
  async goHome(): Promise<void> {
    await this.sendHidEvent(HID.SYSTEM, new Uint8Array([SystemButton.HOME]));
  }

  /** Wake up the device if it is sleeping. */
  async wakeUp(): Promise<void> {
    await this.sendHidEvent(HID.SYSTEM, new Uint8Array([SystemButton.WAKE]));
  }
}

/**
 * Human interface device descriptors.
 * @see https://www.usb.org/hid
 */
export class HID {
  static readonly VALUES: HID[] = [];

  readonly id: number;

  private constructor(readonly data: Uint8Array) {
    HID.VALUES.push(this);
    this.id = HID.VALUES.length;
  }

  /**
   * 360 x 640 touch screen:
   * 6-bit padding, 2-bit type, 16-bit X coordinate, 16-bit Y coordinate.
   */
  static readonly TOUCH_SCREEN = new HID(new Uint8Array([
    0x05, 0x0D,        // Usage Page (Digitizer)
    0x09, 0x04,        // Usage (Touch Screen)
    0xA1, 0x00,        // Collection (Physical)
    0x09, 0x32,        //   Usage (In Range) - proximity to screen
    0x09, 0x33,        //   Usage (Touch) - contact with screen
    0x15, 0x00,        //   Logical Minimum (0)
    0x25, 0x01,        //   Logical Maximum (1)
    0x75, 0x01,        //   Report Size (1)
    0x95, 0x02,        //   Report Count (2)
    0x81, 0x02,        //   Input (Data, Variable, Absolute)
    0x75, 0x01,        //   Report Size (1)
    0x95, 0x06,        //   Report Count (6) - padding
    0x81, 0x01,        //   Input (Constant)
    0x05, 0x01,        //   Usage Page (Generic)
    0x09, 0x30,        //   Usage (X)
    0x15, 0x00,        //   Logical Minimum (0)
    0x26, 0x68, 0x01,  //   Logical Maximum (360)
    0x75, 0x10,        //   Report Size (16)
    0x95, 0x01,        //   Report Count (1)
    0x81, 0x02,        //   Input (Data, Variable, Absolute)
    0x09, 0x31,        //   Usage (Y)
    0x15, 0x00,        //   Logical Minimum (0)
    0x26, 0x80, 0x02,  //   Logical Maximum (640)
    0x75, 0x10,        //   Report Size (16)
    0x95, 0x01,        //   Report Count (1)
    0x81, 0x02,        //   Input (Data, Variable, Absolute)
    0xC0,              // End Collection
  ]));

  /**
   * 101-key keyboard:
   * 8-bit modifier (left & right CTRL, SHIFT, ALT, GUI), 8-bit keycode.
   */
  static readonly KEYBOARD = new HID(new Uint8Array([
    0x05, 0x01,  // Usage Page (Generic)
    0x09, 0x06,  // Usage (Keyboard)
    0xA1, 0x01,  // Collection (Application)
    0x05, 0x07,  //   Usage Page (Key Codes)
    0x19, 0xE0,  //   Usage Minimum (Left Control)
    0x29, 0xE7,  //   Usage Maximum (Right GUI)
    0x15, 0x00,  //   Logical Minimum (0)
    0x25, 0x01,  //   Logical Maximum (1)
    0x75, 0x01,  //   Report Size (1)
    0x95, 0x08,  //   Report Count (8)
    0x81, 0x02,  //   Input (Data, Variable, Absolute)
    0x19, 0x00,  //   Usage Minimum (0)
    0x29, 0x65,  //   Usage Maximum (101)
    0x15, 0x00,  //   Logical Minimum (0)
    0x25, 0x65,  //   Logical Maximum (101)
    0x75, 0x08,  //   Report Size (8)
    0x95, 0x01,  //   Report Count (1)
    0x81, 0x00,  //   Input (Data, Array, Absolute)
    0xC0,        // End Collection
  ]));

  /** System buttons: 5-bit padding, 3-bit flags (wake, home, back). */
  static readonly SYSTEM = new HID(new Uint8Array([
    0x05, 0x01,        // Usage Page (Generic)
    0x09, 0x80,        // Usage (System Control)
    0xA1, 0x01,        // Collection (Application)
    0x15, 0x00,        //   Logical Minimum (0)
    0x25, 0x01,        //   Logical Maximum (1)
    0x75, 0x01,        //   Report Size (1)
    0x95, 0x01,        //   Report Count (1)
    0x09, 0x83,        //   Usage (Wake)
    0x81, 0x06,        //   Input (Data, Variable, Relative)
    0xC0,              // End Collection
    0x05, 0x0C,        // Usage Page (Consumer)
    0x09, 0x01,        // Usage (Consumer Control)
    0xA1, 0x01,        // Collection (Application)
    0x15, 0x00,        //   Logical Minimum (0)
    0x25, 0x01,        //   Logical Maximum (1)
    0x75, 0x01,        //   Report Size (1)
    0x95, 0x01,        //   Report Count (1)
    0x0A, 0x23, 0x02,  //   Usage (Home)
    0x81, 0x06,        //   Input (Data, Variable, Relative)
    0x0A, 0x24, 0x02,  //   Usage (Back)
    0x81, 0x06,        //   Input (Data, Variable, Relative)
    0x75, 0x01,        //   Report Size (1)
    0x95, 0x05,        //   Report Count (5) - padding
    0x81, 0x01,        //   Input (Constant)
    0xC0,              // End Collection
  ]));
}

/** Point with x and y coordinates. */
export class Point {
  constructor(readonly x: number, readonly y: number) {}
}

/** Keyboard key modifier. */
export enum KeyModifier {
  CTRL = 0b0001,
  SHIFT = 0b0010,
  ALT = 0b0100,
  GUI = 0b1000,
}

/**
 * Keyboard keys with their key codes and HID usages.
 * @see https://source.android.com/devices/input/keyboard-devices
 */
export class Key {
  private constructor(readonly code: string, readonly usage: number,
                      readonly modifiers: KeyModifier[] = []) {}

  // Special keys
  static readonly ENTER = new Key('enter', 0x28);
  static readonly TAB = new Key('tab', 0x2B);
  static readonly SPACE = new Key('space', 0x2C);
  static readonly RIGHT = new Key('right', 0x4F);
  static readonly LEFT = new Key('left', 0x50);
  static readonly DOWN = new Key('down', 0x51);
  static readonly UP = new Key('up', 0x52);

  // Map of known keys
  private static readonly CODES: Map<string, Key> = (() => {
    const map = new Map<string, Key>();

    // Letters (case-sensitive)
    for (let i = 0; i < 26; i++) {
      const upperChar = String.fromCharCode(65 + i);
      const lowerChar = upperChar.toLowerCase();
      const usage = 0x04 + i;  // A = 0x04
      map.set(lowerChar, new Key(lowerChar, usage));
      map.set(upperChar, new Key(upperChar, usage, [KeyModifier.SHIFT]));
    }

    // Numbers
    map.set('1', new Key('1', 0x1E));
    map.set('2', new Key('2', 0x1F));
    map.set('3', new Key('3', 0x20));
    map.set('4', new Key('4', 0x21));
    map.set('5', new Key('5', 0x22));
    map.set('6', new Key('6', 0x23));
    map.set('7', new Key('7', 0x24));
    map.set('8', new Key('8', 0x25));
    map.set('9', new Key('9', 0x26));
    map.set('0', new Key('0', 0x27));

    // Additional keys
    map.set('enter', Key.ENTER);
    map.set('tab', Key.TAB);
    map.set('space', Key.SPACE);
    map.set(' ', Key.SPACE);
    map.set('right', Key.RIGHT);
    map.set('left', Key.LEFT);
    map.set('down', Key.DOWN);
    map.set('up', Key.UP);
    map.set('@', new Key('@', 0x1F, [KeyModifier.SHIFT]));
    map.set('-', new Key('-', 0x2D));
    map.set('_', new Key('_', 0x2D, [KeyModifier.SHIFT]));
    map.set('+', new Key('+', 0x2E, [KeyModifier.SHIFT]));
    map.set('.', new Key('.', 0x37));

    return map;
  })();

  static get(code: string): Key|undefined {
    return Key.CODES.get(code) || Key.CODES.get(code.toLowerCase());
  }
}
