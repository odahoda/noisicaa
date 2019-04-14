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

declare name "Noise";
declare uri "builtin://noise";
declare output0_name "out";
declare output0_display_name "Output";
declare output0_type "AUDIO";

import("stdfaust.lib");

whitenoise = no.noise;
pinknoise = no.pink_noise;

type = nentry(
	  "type[display_name:Type][style:menu{'White noise':0.0; 'Pink noise':1.0}]",
	  0.0, 0.0, 1.0, 1.0);

noise = whitenoise, pinknoise : select2(type);

process = noise;
