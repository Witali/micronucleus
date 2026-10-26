/* Block64 protocol operation numbers, memory states and limits. */
#ifndef BLOCK64_PROTOCOL_INC
#define BLOCK64_PROTOCOL_INC
/* State values are intentionally clustered for short busy checks:
   idle/done/error=0..2, run=3, active write phases=4..7. */
#define ST_IDLE 0
#define ST_DONE 1
#define ST_ERROR 2
#define ST_RUN 3
#define ST_RECEIVE 4
#define ST_WRITE_EEPROM 5
#define ST_FLASH_WAIT_PREP 6
#define ST_SPM_WAIT_SENT 7
/* ST_FLASH_WAIT_PREP serves both erase and write. MEM_PROGRESS distinguishes them. */
#define BLOCK64_VERSION_MAJOR 0x03
#define BLOCK64_VERSION_MINOR 0x03
#define BLOCK64_PROTO_MARKER 0x33
#define BLOCK64_STATUS_BYTES 8
#define OP_READ 0x10
#define OP_WRITE 0x11
#define OP_GET_STATUS 0x12
#define OP_RUN 0x13
#define OP_ERASE_PAGE 0x14
#define MEM_FLASH 0
#define MEM_EEPROM 1
#define RESULT_OK 0
#define RESULT_BUSY 1
#define RESULT_BOUNDS 2
#define RESULT_FAIL 3
#define EP0_NAK 0x5a
#define EMPTY_MESSAGE 0xff
#define EP0_MAX_PACKET 8
#define USB_PID_ACK 0xd2
#define USB_PID_DATA1 0x4b
#define USB_PID_OUT 0xe1
/* Bounded SOP wait; exact end-EOP deadline is checked by bus timing tests. */
#define USB_ACK_WAIT_POLLS 35
#define OWNER_FLASH 1
#define OWNER_RUN 2
#define OWNER_EEPROM 3
#define OWNER_ACKED 0x80
#define BLOCK_MAX 64
#define RESET_RJMP (0xc000 | (((BOOT_AT/2)-1) & 0x0fff))
#endif /* BLOCK64_PROTOCOL_INC */
