<CsoundSynthesizer>
<CsOptions>
-odac
</CsOptions>
<CsInstruments>

sr = 44100
ksmps = 32
nchnls = 2
0dbfs  = 1

instr 1

iNote = notnum()

iTable = 1
iVolume = 1
iFilter = 0

; <group>
; count=1

if (iNote >= 0 && iNote <= 54) then
  ; <region> sample=samples/c2.wav
  ; lokey=0 hikey=54 pitch_keycenter=60
  iTable = 7
  iNoteKeyCenter = 60

elseif (iNote >= 55 && iNote <= 59) then
  ; <region> sample=samples/b1.wav
  ; lokey=55 hikey=59 pitch_keycenter=59
  ; volume=2.618
  iTable = 4
  iNoteKeyCenter = 59
  iVolume = db(2.618)

elseif (iNote >= 60 && iNote <= 61) then
  ; <region> sample=samples/c2.wav
  ; lokey=60 hikey=61 pitch_keycenter=60
  ; volume=2.618
  iTable = 7
  iNoteKeyCenter = 60
  iVolume = db(2.618)

elseif (iNote >= 62 && iNote <= 62) then
  ; <region> sample=samples/d2.wav
  ; lokey=62 hikey=62 pitch_keycenter=62
  ; volume=1.463
  iTable = 10
  iNoteKeyCenter = 62
  iVolume = db(1.463)

elseif (iNote >= 63 && iNote <= 64) then
  ; <region> sample=samples/e2.wav
  ; lokey=63 hikey=64 pitch_keycenter=64
  ; volume=2.618
  iTable = 13
  iNoteKeyCenter = 64
  iVolume = db(2.618)

elseif (iNote >= 65 && iNote <= 66) then
  ; <region> sample=samples/f2.wav
  ; lokey=65 hikey=66 pitch_keycenter=65
  ; volume=2.618
  iTable = 16
  iNoteKeyCenter = 65
  iVolume = db(2.618)

elseif (iNote >= 67 && iNote <= 68) then
  ; <region> sample=samples/g2.wav
  ; lokey=67 hikey=68 pitch_keycenter=67
  ; volume=2.618
  iTable = 20
  iNoteKeyCenter = 67
  iVolume = db(2.618)

elseif (iNote >= 69 && iNote <= 70) then
  ; <region> sample=samples/a2.wav
  ; lokey=69 hikey=70 pitch_keycenter=69
  ; volume=2.618
  iTable = 2
  iNoteKeyCenter = 69
  iVolume = db(2.618)

elseif (iNote >= 71 && iNote <= 71) then
  ; <region> sample=samples/b2.wav
  ; lokey=71 hikey=71 pitch_keycenter=71
  ; volume=2.618
  iTable = 5
  iNoteKeyCenter = 71
  iVolume = db(2.618)

elseif (iNote >= 72 && iNote <= 73) then
  ; <region> sample=samples/c3.wav
  ; lokey=72 hikey=73 pitch_keycenter=72
  ; volume=2.618
  iTable = 8
  iNoteKeyCenter = 72
  iVolume = db(2.618)

elseif (iNote >= 74 && iNote <= 75) then
  ; <region> sample=samples/d3.wav
  ; lokey=74 hikey=75 pitch_keycenter=74
  ; volume=2.618
  iTable = 11
  iNoteKeyCenter = 74
  iVolume = db(2.618)

elseif (iNote >= 76 && iNote <= 76) then
  ; <region> sample=samples/e3.wav
  ; lokey=76 hikey=76 pitch_keycenter=76
  ; volume=2.618
  iTable = 14
  iNoteKeyCenter = 76
  iVolume = db(2.618)

elseif (iNote >= 77 && iNote <= 78) then
  ; <region> sample=samples/f3.wav
  ; lokey=77 hikey=78 pitch_keycenter=77
  ; volume=2.618
  iTable = 17
  iNoteKeyCenter = 77
  iVolume = db(2.618)

elseif (iNote >= 79 && iNote <= 80) then
  ; <region> sample=samples/g3.wav
  ; lokey=79 hikey=80 pitch_keycenter=79
  ; volume=2.618
  iTable = 21
  iNoteKeyCenter = 79
  iVolume = db(2.618)

elseif (iNote >= 81 && iNote <= 82) then
  ; <region> sample=samples/a3.wav
  ; lokey=81 hikey=82 pitch_keycenter=81
  ; volume=2.618
  iTable = 3
  iNoteKeyCenter = 81
  iVolume = db(2.618)

elseif (iNote >= 83 && iNote <= 83) then
  ; <region> sample=samples/b3.wav
  ; lokey=83 hikey=83 pitch_keycenter=83
  ; volume=2.618
  iTable = 6
  iNoteKeyCenter = 83
  iVolume = db(2.618)

elseif (iNote >= 84 && iNote <= 85) then
  ; <region> sample=samples/c4.wav
  ; lokey=84 hikey=85 pitch_keycenter=84
  ; volume=2.618
  ; cutoff=8544.8
  iTable = 9
  iNoteKeyCenter = 84
  iVolume = db(2.618)
  iFilter = 8544.8

elseif (iNote >= 86 && iNote <= 87) then
  ; <region> sample=samples/d4.wav
  ; lokey=86 hikey=87 pitch_keycenter=86
  ; volume=-3.157
  iTable = 12
  iNoteKeyCenter = 86
  iVolume = db(-3.157)

elseif (iNote >= 88 && iNote <= 88) then
  ; <region> sample=samples/e4.wav
  ; lokey=88 hikey=88 pitch_keycenter=88
  ; volume=2.618
  iTable = 15
  iNoteKeyCenter = 88
  iVolume = db(2.618)

elseif (iNote >= 89 && iNote <= 89) then
  ; <region> sample=samples/f4.wav
  ; lokey=89 hikey=89 pitch_keycenter=89
  ; volume=2.618
  iTable = 18
  iNoteKeyCenter = 89
  iVolume = db(2.618)

elseif (iNote >= 90 && iNote <= 127) then
  ; <region> sample=samples/c4.wav
  ; lokey=90 hikey=127 pitch_keycenter=84
  ; volume=2.618
  ; cutoff=8544.8
  iTable = 9
  iNoteKeyCenter = 84
  iVolume = db(2.618)
  iFilter = 8544.8

else
  ; nothing to play
endif

iPitch = cpsmidinn(iNote)
iPitchKeyCenter = cpsmidinn(iNoteKeyCenter)
;print iNote, iPitch, iNoteKeyCenter, iPitchKeyCenter

asig loscil 1, iPitch, iTable, iPitchKeyCenter, 0

if (iFilter > 0) then
  asig butterlp asig, iFilter
endif

    outs asig, asig

endin
</CsInstruments>
<CsScore>
;f0 3600

f 1 0 0 1 "/storage/home/share/instruments/balafon/samples/a1.wav" 0 0 0
f 2 0 0 1 "/storage/home/share/instruments/balafon/samples/a2.wav" 0 0 0
f 3 0 0 1 "/storage/home/share/instruments/balafon/samples/a3.wav" 0 0 0
f 4 0 0 1 "/storage/home/share/instruments/balafon/samples/b1.wav" 0 0 0
f 5 0 0 1 "/storage/home/share/instruments/balafon/samples/b2.wav" 0 0 0
f 6 0 0 1 "/storage/home/share/instruments/balafon/samples/b3.wav" 0 0 0
f 7 0 0 1 "/storage/home/share/instruments/balafon/samples/c2.wav" 0 0 0
f 8 0 0 1 "/storage/home/share/instruments/balafon/samples/c3.wav" 0 0 0
f 9 0 0 1 "/storage/home/share/instruments/balafon/samples/c4.wav" 0 0 0
f 10 0 0 1 "/storage/home/share/instruments/balafon/samples/d2.wav" 0 0 0
f 11 0 0 1 "/storage/home/share/instruments/balafon/samples/d3.wav" 0 0 0
f 12 0 0 1 "/storage/home/share/instruments/balafon/samples/d4.wav" 0 0 0
f 13 0 0 1 "/storage/home/share/instruments/balafon/samples/e2.wav" 0 0 0
f 14 0 0 1 "/storage/home/share/instruments/balafon/samples/e3.wav" 0 0 0
f 15 0 0 1 "/storage/home/share/instruments/balafon/samples/e4.wav" 0 0 0
f 16 0 0 1 "/storage/home/share/instruments/balafon/samples/f2.wav" 0 0 0
f 17 0 0 1 "/storage/home/share/instruments/balafon/samples/f3.wav" 0 0 0
f 18 0 0 1 "/storage/home/share/instruments/balafon/samples/f4.wav" 0 0 0
f 19 0 0 1 "/storage/home/share/instruments/balafon/samples/g1.wav" 0 0 0
f 20 0 0 1 "/storage/home/share/instruments/balafon/samples/g2.wav" 0 0 0
f 21 0 0 1 "/storage/home/share/instruments/balafon/samples/g3.wav" 0 0 0

i 1 0 0.2 0
;i 1 + 0.2 1
;i 1 + 0.2 2
;i 1 + 0.2 3
;i 1 + 0.2 4
;i 1 + 0.2 5
;i 1 + 0.2 6
;i 1 + 0.2 7
;i 1 + 0.2 8
;i 1 + 0.2 9
;i 1 + 0.2 10
;i 1 + 0.2 11
;i 1 + 0.2 12
;i 1 + 0.2 13
;i 1 + 0.2 14
;i 1 + 0.2 15
;i 1 + 0.2 16
;i 1 + 0.2 17
;i 1 + 0.2 18
;i 1 + 0.2 19
;i 1 + 0.2 20
;i 1 + 0.2 21
;i 1 + 0.2 22
;i 1 + 0.2 23
;i 1 + 0.2 24
;i 1 + 0.2 25
;i 1 + 0.2 26
;i 1 + 0.2 27
;i 1 + 0.2 28
;i 1 + 0.2 29
;i 1 + 0.2 30
;i 1 + 0.2 31
;i 1 + 0.2 32
;i 1 + 0.2 33
;i 1 + 0.2 34
;i 1 + 0.2 35
;i 1 + 0.2 36
;i 1 + 0.2 37
;i 1 + 0.2 38
;i 1 + 0.2 39
;i 1 + 0.2 40
;i 1 + 0.2 41
;i 1 + 0.2 42
;i 1 + 0.2 43
;i 1 + 0.2 44
;i 1 + 0.2 45
;i 1 + 0.2 46
;i 1 + 0.2 47
;i 1 + 0.2 48
;i 1 + 0.2 49
;i 1 0 1 50
;i 1 + 1 51
;i 1 + 1 52
;i 1 + 1 53
;i 1 + 1 54
;i 1 + 1 55
;i 1 + 1 56
;i 1 + 1 57
;i 1 + 1 58
;i 1 + 1 59
;i 1 + 1 60
;i 1 + 1 61
;i 1 + 1 62
;i 1 + 1 63
;i 1 + 1 64
;i 1 + 1 65
;i 1 + 1 66
;i 1 + 1 67
;i 1 + 1 68
;i 1 + 1 69
;i 1 + 1 70
;i 1 + 1 71
;i 1 + 1 72
;i 1 + 1 73
;i 1 + 1 74
;i 1 + 1 75
;i 1 + 1 76
;i 1 + 1 77
;i 1 + 1 78
;i 1 + 1 79
;i 1 + 1 80
;i 1 + 1 81
;i 1 + 1 82
;i 1 + 1 83
;i 1 + 1 84
;i 1 + 1 85
;i 1 + 1 86
;i 1 + 1 87
;i 1 + 1 88
;i 1 + 1 89
;i 1 + 1 90
;i 1 + 1 91
;i 1 + 1 92
;i 1 + 1 93
;i 1 + 1 94
;i 1 + 1 95
;i 1 + 0.2 96
;i 1 + 0.2 97
;i 1 + 0.2 98
;i 1 + 0.2 99
;i 1 + 0.2 100
;i 1 + 0.2 101
;i 1 + 0.2 102
;i 1 + 0.2 103
;i 1 + 0.2 104
;i 1 + 0.2 105
;i 1 + 0.2 106
;i 1 + 0.2 107
;i 1 + 0.2 108
;i 1 + 0.2 109
;i 1 + 0.2 110
;i 1 + 0.2 111
;i 1 + 0.2 112
;i 1 + 0.2 113
;i 1 + 0.2 114
;i 1 + 0.2 115
;i 1 + 0.2 116
;i 1 + 0.2 117
;i 1 + 0.2 118
;i 1 + 0.2 119
;i 1 + 0.2 120
;i 1 + 0.2 121
;i 1 + 0.2 122
;i 1 + 0.2 123
;i 1 + 0.2 124
;i 1 + 0.2 125
;i 1 + 0.2 126
;i 1 + 0.2 127

e 3600
</CsScore>
</CsoundSynthesizer>
