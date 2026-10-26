/* Board layout and memory-mapped hardware register addresses for ATtiny88.
   Change here when porting; 16 MHz USB timing must be re-audited on new MCUs. */
#ifndef T88_DEVICE_CONFIG_INC
#define T88_DEVICE_CONFIG_INC

#ifndef BOOT_AT
/* Explicit development room for ACK/replay and control-transfer ownership. */
#define BOOT_AT 0x18c0
#endif
#define T88_FLASH_BYTES 8192
#define T88_FLASH_PAGE_BYTES 64
#define T88_EEPROM_BYTES 64
#define T88_RAMSTART 0x0100
#define T88_RAMEND 0x02ff
#define T88_F_CPU_HZ 16000000
/* The ATtiny88 reset value of SPL/SPH is RAMEND (datasheet section 4.6).
   1 removes redundant 8 bytes on hardware reset, but a direct software jump
   into the bootloader without reset is then unsupported. Set 0 for that use. */
#ifndef T88_ASSUME_RESET_STACK_INIT
#define T88_ASSUME_RESET_STACK_INIT 1
#endif
/* Registers below are I/O addresses, except explicitly marked MEM. */
#define T88_IO_PIND 0x09
#define T88_IO_DDRD 0x0a
#define T88_IO_PORTD 0x0b
#define T88_IO_PCIFR 0x1b
#define T88_IO_EECR 0x1f
#define T88_IO_EEDR 0x20
#define T88_IO_EEARL 0x21
#define T88_IO_MCUSR 0x34
#define T88_IO_SPMCSR 0x37
#define T88_IO_SPL 0x3d
#define T88_IO_SPH 0x3e
#define T88_IO_SREG 0x3f
#define T88_IO_GPIOR0 0x1e
#define T88_MEM_WDTCSR 0x0060
#define T88_MEM_PCICR 0x0068
#define T88_MEM_PCMSK2 0x006d
#define T88_USB_DMINUS_BIT 1
#define T88_USB_DPLUS_BIT 2
#define T88_USB_PIN_CHANGE_FLAG 2

#define MEM_STATE 0x0139
#define USB_TX_ACK_WINDOW 0x012c
#define CTX_TX_ACK_WINDOW 44
#define CONTROL_OWNER 0x012d
#define CTX_CONTROL_OWNER 45
#define CTX_TOKEN_CRC5 46
#define USB_TOKEN_CRC5 0x012e
#define MEM_TYPE 0x0130
#define MEM_ADDR_LO 0x0131
#define MEM_ADDR_HI 0x0132
#define MEM_REMAIN 0x0133
#define MEM_INDEX 0x0134
#define MEM_TOTAL 0x0135
#define MEM_STATUS 0x0138
#define MEM_PROGRESS 0x0136
#define MEM_EXPECT_PID 0x0137  /* USB DATA1 after SETUP, toggles per accepted OUT */
#define MEM_BUFFER 0x0140   /* one 64-byte SRAM page, 0x0140-0x017f */
/* Live status response at SRAM 0x0138..0x013F: MEM_STATUS, MEM_STATE,
   followed by six immutable fields initialized from Flash BOOT_AT+2. */

#endif /* T88_DEVICE_CONFIG_INC */
