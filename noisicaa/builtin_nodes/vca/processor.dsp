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

declare name "VCA";
declare uri "builtin://vca";
declare input0_name "in";
declare input0_display_name "Audio Input";
declare input0_type "AUDIO";
declare input1_name "amp";
declare input1_display_name "Amplification";
declare input1_type "ARATE_CONTROL";
declare input1_float_value "0.0 1.0 0.0";
declare output0_name "out";
declare output0_display_name "Audio Output";
declare output0_type "AUDIO";

import("stdfaust.lib");

smooth = hslider(
	  "smooth[display_name:Smooth]",
	  0.0, 0.0, 1.0, 0.01);

vca(in, amp) = si.smooth(ba.tau2pole(smooth * 0.05), amp) * in;

process = vca;
