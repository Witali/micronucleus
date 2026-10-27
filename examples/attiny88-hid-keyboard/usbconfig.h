/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TINY88_USBCONFIG_H
#define TINY88_USBCONFIG_H

#if F_CPU != 16000000UL
#error "This example requires the MH-Tiny88 external 16 MHz clock"
#endif

#define USB_CFG_IOPORTNAME D
#define USB_CFG_DMINUS_BIT 1
#define USB_CFG_DPLUS_BIT 2
#define USB_CFG_CLOCK_KHZ (F_CPU / 1000)

/* PD2 is INT0 on ATtiny88. Use the highest-priority external interrupt. */
#define USB_INTR_CFG EICRA
#define USB_INTR_CFG_SET ((1 << ISC00) | (1 << ISC01))
#define USB_INTR_CFG_CLR 0
#define USB_INTR_ENABLE EIMSK
#define USB_INTR_ENABLE_BIT INT0
#define USB_INTR_PENDING EIFR
#define USB_INTR_PENDING_BIT INTF0
#define USB_INTR_VECTOR INT0_vect

#define USB_CFG_HAVE_INTRIN_ENDPOINT 1
#define USB_CFG_HAVE_INTRIN_ENDPOINT3 0
#define USB_CFG_INTR_POLL_INTERVAL 10
#define USB_CFG_IMPLEMENT_HALT 1
#define USB_CFG_IMPLEMENT_FN_WRITE 1
#define USB_CFG_IMPLEMENT_FN_READ 0
#define USB_CFG_IMPLEMENT_FN_WRITEOUT 0
#define USB_CFG_IS_SELF_POWERED 0
#define USB_CFG_MAX_BUS_POWER 100
#define USB_CFG_HAVE_FLOWCONTROL 0
#define USB_CFG_LONG_TRANSFERS 0
#define USB_CFG_CHECK_CRC 0
#define USB_CFG_CHECK_DATA_TOGGLING 0
#define USB_CFG_HAVE_MEASURE_FRAME_LENGTH 0
#define USB_COUNT_SOF 0
#define USB_USE_FAST_CRC 0

/* V-USB's shared keyboard PID; only the OS class driver is used, no serial. */
#define USB_CFG_VENDOR_ID 0xc0, 0x16
#define USB_CFG_DEVICE_ID 0xdb, 0x27
#define USB_CFG_DEVICE_VERSION 0x00, 0x01
#define USB_CFG_VENDOR_NAME 'M','i','c','r','o','N','u','c','l','e','u','s'
#define USB_CFG_VENDOR_NAME_LEN 12
#define USB_CFG_DEVICE_NAME 'T','i','n','y','8','8',' ','K','e','y','b','o','a','r','d'
#define USB_CFG_DEVICE_NAME_LEN 15
#define USB_CFG_DEVICE_CLASS 0
#define USB_CFG_DEVICE_SUBCLASS 0
#define USB_CFG_INTERFACE_CLASS 3
#define USB_CFG_INTERFACE_SUBCLASS 1
#define USB_CFG_INTERFACE_PROTOCOL 1
#define USB_CFG_HID_REPORT_DESCRIPTOR_LENGTH 63

/* Supply a configuration without advertising unsupported remote wakeup. */
#define USB_CFG_DESCR_PROPS_CONFIGURATION 34

#ifndef __ASSEMBLER__
void keyboard_usb_reset(unsigned char reset_starts);
#endif
#define USB_RESET_HOOK(reset_starts) keyboard_usb_reset(reset_starts)

#endif
