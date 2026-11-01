#ifndef _AVR_IO_H_
#define _AVR_IO_H_
/* Portable subset extracted from Microchip ATtiny_DFP-3.4.278 and AVR-LibC,
   for assembler only; validated official addresses are documented in README. */
#define _SFR_IO8(x) (x)
#define _SFR_MEM8(x) (x)
#define _SFR_IO_ADDR(x) (x)
#define _SFR_MEM_ADDR(x) (x)
#define SPM_PAGESIZE 64
#define E2END 0x3f
#define RAMSTART 0x100
#define RAMEND 0x2ff
#define PD1 1
#define PD2 2
#define PCINT18 2
#define PCIE2 2
#define WDCE 4
#define WDE 3
#define SELFPRGEN 0
#define PGERS 1
#define PGWRT 2
#define CTPB 4
#define SREG 0x3f
#define SPL 0x3d
#define SPH 0x3e
#define MCUSR _SFR_IO8(0x34)
#define GPIOR0 _SFR_IO8(0x1e)
#define GPIOR2 _SFR_IO8(0x2b)
#define WDTCSR _SFR_MEM8(0x60)
#define DDRD _SFR_IO8(0x0a)
#define PORTD _SFR_IO8(0x0b)
#define PIND _SFR_IO8(0x09)
#define PCMSK2 _SFR_MEM8(0x6d)
#define PCICR _SFR_MEM8(0x68)
#define PCIFR _SFR_IO8(0x1b)
#define PCIF2 2
#define SPMCSR _SFR_IO8(0x37)
#define EECR _SFR_IO8(0x1f)
#define EEPE 1
#define EEMPE 2
#define EERE 0
#define EEDR _SFR_IO8(0x20)
#define EEARL _SFR_IO8(0x21)
#define SIGNATURE_1 0x93
#define SIGNATURE_2 0x11
#define SREG_Z 1
#define SREG_C 0
#endif
