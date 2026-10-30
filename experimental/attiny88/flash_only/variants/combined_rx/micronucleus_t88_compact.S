/* Composed receive experiment; all control and memory logic has one owner.
 * Measure at a noncanonical placement. No recognized release profile is added.
 * The PHY calibrates its own five-cycle token-to-DATA wait. */
#define USB_PHY_SOURCE "../variants/combined_rx/vusb_phy.inc"
#define USB_NEXT_DATA_WAIT_COUNT 27
/* A measurement at any placement must remain unknown to the host client. */
#define BOOT_VERSION_BCD 0xffff
#include "../../source/micronucleus_t88_compact.S"
