/* Experimental compact ACK reader; normal DATA still uses the control PHY.
 * No recognized host profile or hardware-programming image is introduced. */
#define USB_RX_ACK_TERMINAL 1
#define USB_PHY_SOURCE "../variants/combined_rx/vusb_phy.inc"
/* Register-cached address shortens token parsing by two clocks. */
#define USB_NEXT_DATA_WAIT_COUNT 28
#define BOOT_VERSION_BCD 0xffff
#include "../../source/micronucleus_t88_compact.S"
