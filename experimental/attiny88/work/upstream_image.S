.section .text
.org 0x1a40
.global upstream_start
upstream_start:
.incbin "/mnt/data/micronucleus_t88_optimization/reference/t88_default_upstream.bin"
