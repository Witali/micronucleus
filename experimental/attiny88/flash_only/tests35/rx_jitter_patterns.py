"""Legal extremal differential-edge jitter fixtures for a low-speed function.

USB2 Table 7-10 TDJR1/TDJR2 are 75/45 ns at the upstream-facing receiver.
Table 7-5 and 7.1.15.1 include source frequency error in this input budget;
receiver clock error is a separate allowance. A full jitter amplitude must not
be stacked blindly on an already shifted source frequency.

These are corner regressions, not an exhaustive proof over arbitrary histories.
They change actual differential transitions, not every same-level bit boundary.
"""
from copy import copy

PATTERNS_NS = {
    'next': (-37.5, 37.5),
    'paired': (-22.5, -22.5, 22.5, 22.5),
    'joint': (-37.5, 37.5, 7.5, -7.5),
    'alternating_joint': (-37.5, 37.5, -37.5, -7.5),
}
LIMITS_NS = {1: 75.0, 2: 45.0}


def differential_edges(wave):
    """Return (physical bit index, actual time) until the first SE0 only."""
    edges = []; before = 2
    for index, (when, level) in enumerate(zip(wave.boundaries, wave.levels)):
        if level == 0: break
        assert level in (2, 4), ('non differential data', index, level)
        if level != before: edges.append((index, when))
        before = level
    assert edges and edges[0][0] == 0, 'fixture expects complete SYNC/SOP'
    return edges


def interval_errors(wave, cpu_hz=16_000_000, nominal_rate=1_500_000):
    """Errors include source frequency relative to nominal, as Table 7-5 does."""
    edges = differential_edges(wave); clock_ns = 1e9/cpu_hz
    nominal_ns = 1e9/nominal_rate; result = {}
    for distance, limit in LIMITS_NS.items():
        errors = [(right[1]-left[1])*clock_ns-(right[0]-left[0])*nominal_ns
                  for left, right in zip(edges, edges[distance:])]
        assert errors and all(abs(error) <= limit+1e-6 for error in errors), (distance, min(errors), max(errors))
        result[distance] = (min(errors), max(errors))
    return result


def jittered(wave, name, rotation=0, sign=1, cpu_hz=16_000_000,
             nominal_rate=1_500_000):
    """Copy a uniform, stuffed wire and maximize this legal periodic template.

    At nominal rate the template reaches exact 75/45 ns corners. At a shifted
    source rate a single scale is solved against every actual next/paired
    interval. Thus accumulated frequency error consumes the same total budget,
    rather than being added on top of it. The first edge remains at wave.start;
    entry-phase sweeps supply the independent common phase.

    EOP follows the last edge's phase, retaining the original SE0 width and J
    recovery. A multi-packet caller must measure its next SOP gap from that new
    physical EOP-J, rather than from the original unjittered time.
    """
    assert sign in (-1, 1)
    pattern = PATTERNS_NS[name]; rotation %= len(pattern)
    edges = differential_edges(wave); clock_ns = 1e9/cpu_hz
    nominal_ns = 1e9/nominal_rate; period_ns = wave.period*clock_ns
    ndata = wave.levels.index(0)
    for index in range(ndata):
        assert abs(wave.boundaries[index]-(wave.start+index*wave.period)) < 1e-6, 'input already jittered'
    offsets = [sign*(pattern[(i+rotation)%len(pattern)]-pattern[rotation]) for i in range(len(edges))]
    lower = 0.0; upper = 1.0
    for distance, limit in LIMITS_NS.items():
        for index in range(len(edges)-distance):
            bits = edges[index+distance][0]-edges[index][0]
            frequency = bits*(period_ns-nominal_ns)
            change = offsets[index+distance]-offsets[index]
            if change:
                limits = sorted(((-limit-frequency)/change, (limit-frequency)/change))
                lower = max(lower, limits[0]); upper = min(upper, limits[1])
            else:
                assert abs(frequency) <= limit+1e-7, 'source frequency alone exceeds input jitter budget'
    assert upper >= lower-1e-9 and upper >= 0, 'no legal scale at this source frequency'
    scale = min(1.0, max(0.0, upper))
    phase_at = {edge[0]: scale*offset/clock_ns for edge, offset in zip(edges, offsets)}
    out = copy(wave); out.boundaries = []; current = 0.0
    for index in range(ndata):
        if index in phase_at: current = phase_at[index]
        out.boundaries.append(wave.start+index*wave.period+current)
    eop_shift = current
    out.boundaries.extend(when+eop_shift for when in wave.boundaries[ndata:])
    out.levels = list(wave.levels); out.labels = list(wave.labels)
    out.end = wave.end+eop_shift
    assert all(a < b for a,b in zip(out.boundaries,out.boundaries[1:])), 'nonmonotone cells'
    out.pin_edges = []; previous = 2
    for when, level in zip(out.boundaries,out.levels):
        if (previous^level)&4: out.pin_edges.append(when)
        previous = level
    out.jitter_certificate = dict(pattern=name, rotation=rotation, sign=sign,
                                  scale=scale, total_errors_ns=interval_errors(out,cpu_hz,nominal_rate),
                                  cpu_hz=cpu_hz, nominal_rate=nominal_rate)
    return out


def corners(wave, **kwargs):
    """Yield all 28 phase/sign variants of the four short edge templates."""
    for name, pattern in PATTERNS_NS.items():
        for rotation in range(len(pattern)):
            for sign in (-1,1):
                yield jittered(wave,name,rotation,sign,**kwargs)
