/* Benchmark-only access checks. No changes to the timed USB receiver.
 * Flash READ: [0x0000,0x2000); mutation: eight pages [0x1800,0x1a00).
 * EEPROM READ/WRITE: [0,64). ERASE_PAGE remains Flash-only; RUN is rejected.
 * Called after the ordinary length/type/upper-bound checks and before the
 * ordinary idle/EEPROM-ready interlock. Preserve R16, R22:R23 and R24.
 * Return C=1 for allowed access, C=0 otherwise. Scratch R18 only.
 */
benchmark_validate_access:
    ldd     r18, Y+23
    cpi     r18, 0xc0
    brne    benchmark_validate_mutation
    ldd     r18, Y+24
    cpi     r18, OP_READ
    breq    benchmark_access_allowed
    rjmp    benchmark_access_denied
benchmark_validate_mutation:
    cpi     r18, 0x40
    brne    benchmark_access_denied
    ldd     r18, Y+24
    cpi     r18, OP_WRITE
    breq    benchmark_validate_memory
    cpi     r18, OP_ERASE_PAGE
    brne    benchmark_access_denied
    tst     r16
    brne    benchmark_access_denied
benchmark_validate_memory:
    tst     r16
    brne    benchmark_access_allowed /* EEPROM bound was checked already. */
    cpi     r24, 64
    brne    benchmark_access_denied
    mov     r18, r22
    andi    r18, 0x3f
    brne    benchmark_access_denied
    cpi     r23, 0x18
    brlo    benchmark_access_denied
    cpi     r23, 0x1a
    brsh    benchmark_access_denied
benchmark_access_allowed:
    sec
    ret
benchmark_access_denied:
    clc
    ret

/* Defense at the final address builder. The SPM command in R18 is live;
 * inspect only ZH. This executes before OUT SPMCSR, so its four-cycle
 * enable-to-SPM window remains untouched. Every Flash page fits this range.
 */
benchmark_validate_spm_address:
    cpi     r31, 0x18
    brlo    benchmark_nvm_fault
    cpi     r31, 0x1a
    brsh    benchmark_nvm_fault
    ret

/* This can be reached only if internal state violates an already checked
 * address invariant. Stop before an NVM trigger; RESET returns to the
 * installed loader. No host request can resume a faulted benchmark app.
 */
benchmark_nvm_fault:
    clr     r1
    rjmp    benchmark_nvm_fault
