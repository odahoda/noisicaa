/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

declare name "Oscillator";
declare uri "builtin://oscillator";
declare input0_name "freq";
declare input0_display_name "Frequency (Hz)";
declare input0_float_value "1 20000 440";
declare input0_scale "log";
declare input0_type "ARATE_CONTROL,AUDIO";
declare output0_name "out";
declare output0_display_name "Output";
declare output0_type "ARATE_CONTROL,AUDIO";

import("stdfaust.lib");

sine = os.osc;
sawtooth = os.sawtooth;
square = os.square;

shape = nentry(
	  "waveform[display_name:Waveform][style:menu{'Sine':0.0; 'Sawtooth':1.0; 'Square':2.0}]",
	  0.0, 0.0, 2.0, 1.0);

oscillator(freq) = sine(freq), sawtooth(freq), square(freq) : select3(shape);

process = oscillator;
