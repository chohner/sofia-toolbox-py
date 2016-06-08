"""
Generator functions:
- Wave generator (wgc)
- Modal radial filters (mf)
"""
import numpy as _np
from .sph import bn, bn_npf, sphankel, sph_harm


def wgc(N, r, ac, fs, F_NFFT, az, el, **kargs):
    """
    Wave Generator Core:
    Returns Spatial Fourier Coefficients Pnm and kr vector
    Pnm, kr = sofia.wgc(N, r, ac, FS, NFFT, AZ, EL)

    Optional keyword parameters: t, c, wavetype, ds, lSegLim, uSegLim, SeqN
    ------------------------------------------------------------------------
    Pnm      Spatial Fourier Coefficients
             Columns : nm coeff
             Rows    : FFT bins
    kr       kr-Vector
             Can also be a matrix [krm; krs] for rigid sphere configurations:
             [1,:] => krm referring to the Microphone Radius
             [2,:] => krs referring to the Sphere Radius (Scatterer)
    ------------------------------------------------------------------------
    N        Maximum transform order
    r        Microphone Radius
             Can also be a vector for rigid/dual sphere configurations:
             [1,1] => rm  Microphone Radius
             [2,1] => rs  Sphere Radius or Microphone2 Radius
             ! If only one radius (rm) is given using a Rigid/Dual Sphere
               Configuration: rs = rm and only one kr-vector is returned!
    ac       Array Configuration
             0  Open Sphere with p Transducers (NO plc!)
             1  Open Sphere with pGrad Transducers
             2  Rigid Sphere with p Transducers
             3  Rigid Sphere with pGrad Transducers (Thx to Nils Peters!)
             4  Dual Open Sphere with p Transducers (Thx to Nils Peters!)
    FS       Sampling Frequency
    NFFT     FFT Order (Number of bins) should be 2^x, x=1,2,3,...
    AZ       Azimuth   angle in [DEG] 0-2pi
    EL       Elevation angle in [DEG] 0-pi
    t        Time Delay in s. The delay has: (t*FS) Samples
    c        Speed of sound in [m/s] (Default: 343m/s)
    wavetype Type of the Wave. 0: Plane Wave (default) 1: Spherical Wave
    ds       Distance of the source in [m] (For wavetype = 1 only)
             Warning: If NFFT is smaller than the time the wavefront
             needs to travel from the source to the array, the impulse
             response will by cyclically shifted (cyclic convolution).
    ---
    lSegLim  (Lower Segment Limit) Used by the S/W/G wrapper
    uSegLim  (Upper Segment Limit) Used by the S/W/G wrapper
    SegN     (Sement Order)        Used by the S/W/G wrapper
    """

    print('SOFiA W/G/C - Wave Generator')

    NFFT = F_NFFT / 2 + 1

    SegN = kargs['SegN'] if 'SegN' in kargs else N
    upperSegLim = int(kargs['upperSegLim'] if 'upperSegLim' in kargs else NFFT - 1)
    lowerSegLim = int(kargs['lowerSegLim'] if 'lowerSegLim' in kargs else 0)
    ds = kargs['ds'] if 'ds' in kargs else 1.0
    wavetype = kargs['wavetype'] if 'wavetype' in kargs else 0
    c = kargs['c'] if 'c' in kargs else 343.0
    t = kargs['t'] if 't' in kargs else 0.0

    # TODO: safety checks, source distance

    if isinstance(r, int):
        rm = r
        rs = r
        nor = 1
    else:  # r is matrix
        m, n = r.shape
        if m == 2 | n == 2:
            rs = r[1]
            nor = 2

    w = _np.linspace(0, _np.pi * fs, NFFT)
    # w = 0 breaks stuff ?
    w[0] = w[1]
    k = w / c
    krm = k * rm
    kds = k * rs
    krs = k * ds

    # RADIAL FILTERS
    rfArray = _np.empty([SegN, upperSegLim + 1 - lowerSegLim], dtype=complex)
    for f in range(lowerSegLim, upperSegLim + 1):
        timeShift = _np.exp(- 1j * w[f] * t)

        for n in range(0, SegN):
            if wavetype == 0:    # Plane wave
                rfArray[n][f] = bn(n, krm[f], krs[f], ac) * timeShift
            elif wavetype == 1:  # Spherical wave
                rfArray[n][f] = 4 * _np.pi * -1j * k[f] * timeShift * sphankel(n, kds[f]) * bn_npf(n, krm[f], krs[f], ac)

    # GENERATOR CORE
    Pnm = _np.empty([pow(N + 1, 2), upperSegLim + 1 - lowerSegLim], dtype=complex)
    ctr = 0
    for n in range(0, SegN):
        for m in range(-n, n + 1):
            SHarms = _np.conj(sph_harm(m, n, az, el))
            for f in range(lowerSegLim, upperSegLim + 1):
                Pnm[ctr][f] = SHarms * rfArray[n][f]
            ctr = ctr + 1

    if nor == 2:
        kr = krs
    else:
        kr = krm

    return Pnm, kr


def mf(N, kr, ac, **kargs):
    """M/F Modal radial filters
    dn, beam = mf(N, kr, ac)
    Optional keyword parameters: a_max, plc, fadeover
    ------------------------------------------------------------------------
    dn          Vector of modal 0-N frequency domain filters
    beam        Expected free field On-Axis kr-response
    ------------------------------------------------------------------------
    N           Maximum Order
    kr          Vector or Matrix of kr values
                First Row   (M=1) N: kr values Microphone Radius
                Second Row  (M=2) N: kr values Sphere/Microphone2 Radius
                [kr_mic;kr_sphere] for Rigid/Dual Sphere Configurations
                ! If only one kr-vector is given using a Rigid/Dual Sphere
                Configuration: kr_sphere = kr_mic
    ac          Array Configuration:
                0  Open Sphere with pressure Transducers (NO plc!)
                1  Open Sphere with cardioid Transducers
                2  Rigid Sphere with pressure Transducers
                3  Rigid Sphere with cardioid Transducers
                4  Dual Open Sphere with pressure Transducers
    a_max       Maximum modal amplification limit in [dB]
    plc         OnAxis powerloss-compensation:
                0  Off
                1  Full kr-spectrum plc
                2  Low kr only -> set fadeover
    fadeover    Number of kr values to fade over +/- around min-distance
                gap of powerloss compensated filter and normal N0 filters.
                0 = auto fadeover
    """

    print('SOFiA M/F - Modal radial filter generator')

    # Get optional arguments
    a_maxdB = kargs['a_maxdB'] if 'a_maxdB' in kargs else 0
    a_max = pow(10, (a_maxdB / 20)) if 'a_maxdB' in kargs else 1
    limiteronflag = True if 'a_maxdB' in kargs else False
    plc = kargs['plc'] if 'plc' in kargs else 0
    fadeover = kargs['fadeover'] if 'fadeover' in kargs else 0

    if kr.ndim == 1:
        krN = kr.size
        krM = 1
    else:
        krM, krN = kr.shape

    # TODO: check input

    # TODO: correct krm, krs?
    # TODO: check / replace zeros in krm/krs
    krm = kr
    krs = kr

    OutputArray = _np.empty((N + 1, krN), dtype=_np.complex_)

    # BN filter calculation
    for ctr in range(0, N + 1):
        for ctrb in range(0, krN):
            bnval = bn(ctr, krm[ctrb], krs[ctrb], ac)
            if limiteronflag:
                amplicalc = 2 * a_max / _np.pi * abs(bnval) * _np.arctan(np.pi / (2 * a_max * abs(bnval)))
            else:
                amplicalc = 1
            OutputArray[ctr][ctrb] = amplicalc / bnval

    if(krN < 32 & plc != 0):
        plc = 0
        print("Not enough kr values for PLC fading. PLC disabled.")

    # Powerloss Compensation Filter (PLC)
    noplcflag = 0
    if not plc:
        xi = _np.zeros(krN)
        for ctr in range(0, krN):
            for ctrb in range(0, N + 1):
                xi = xi + (2 * ctrb + 1) * (1 - OutputArray[ctrb][ctr] * bn(ctrb, krm[ctr], krs[ctr], ac))
            xi[ctr] = xi[ctr] * 1 / bn(0, krm[ctr], krs[ctr], ac)
            xi[ctr] = xi[ctr] + OutputArray[0][ctr]

    if plc == 1:  # low kr only
        minDisIDX = _np.argmin(np.abs(OutputArray[0] - xi))
        minDis = _np.abs(OutputArray[0][minDisIDX] - xi[minDisIDX])

        filtergap = 20 * _np.log10(1 / _np.abs(OutputArray[0][minDisIDX] / xi[minDisIDX]))
        print("Filter fade gap: ", filtergap)
        if _np.abs(filtergap) > 20:
            print("Filter fade gap too large, no powerloss compensation applied.")
            noplcflag = 1

        if not noplcflag:
            if abs(filtergap) > 5:
                print("Filtergap is large (> 5 dB).")

            if fadeover == 0:
                fadeover = krN / 100
                if a_maxdB > 0:
                    fadeover = fadeover / _np.ceil(a_max / 4)

            if fadeover > minDis | (minDis + fadeover) > krN:
                if minDisIDX - fadeover < krN - minDisIDX + fadeover:
                    fadeover = minDisIDX
                else:
                    fadeover = krN - minDisIDX

            print("Auto filter size of length: ", fadeover)
        # TODO: Auto reduce filter length
    elif plc == 2:  # Full spectrum
        OutputArray[0] = xi

    normalizeBeam = pow(N + 1, 2)

    BeamResponse = _np.zeros((krN), dtype=_np.complex_)
    for ctr in range(0, krN):
        for ctrb in range(0, N + 1):             # ctrb = n
            for ctrc in range(0, 2 * ctrb + 1):  # ctrc = m
                BeamResponse[ctr] = BeamResponse[ctr] + bn(ctrb, krm[ctr], krs[ctr], ac) * OutputArray[ctrb][ctr]
        BeamResponse[ctr] = BeamResponse[ctr] / normalizeBeam

    return OutputArray, BeamResponse