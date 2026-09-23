"""
Level Meter - the simplest mode, and a template for making your own.

Every face shows six bars in their synesthesia colors, bass at the bottom up to highTop
on top, growing sideways out of two opposite edges of the cube, plus a white border that
flashes on each beat. Use it to check the mic works and to tune the audio settings in
config.py.

HOW TO MAKE YOUR OWN MODE
  1. Copy this file, e.g. to visuals/my_mode.py
  2. Rename the class and change `name`
  3. Rewrite draw(): return a float32 image shaped (self.height, self.width, 3)
     with values 0..1. Use the audio values (listed in audio_analysis.py) to drive
     color, size and movement. visuals/effects.py has ready-made effects.
  That's all: QUBE finds new files in visuals/ by itself, and the next /
  previous buttons include them. Optional, one line each under `name`:
      hue_cycle_seconds = 10    turn every colour round the rainbow every 10 s
      rgb_delay = (0.3, 0.2, 0.1)   red, green, blue lag behind by that many seconds
      order = <number>          move the mode earlier in the rotation
      cycle = False             keep it out of the rotation
"""
import numpy as np

from colors import (bass_color, bass_mid_color, high_color, high_top_color,
                    mid_color, mid_high_color)
from visuals.base import VisualMode


class LevelMeter(VisualMode):
    name = "Level Meter"
    hue_cycle_seconds = 10    # every colour goes round the rainbow once every 10 s
                              # (delete this line to keep each band its own colour)

    def draw(self, audio, dt):
        # A black image for ONE face. Shape: (rows, columns, 3 colors)
        size = self.face
        face = np.zeros((size, size, 3), dtype=np.float32)

        levels = [audio.bass, audio.bassMid, audio.mid, audio.midHigh, audio.high, audio.highTop]
        colors = [bass_color(audio.bass), bass_mid_color(audio.bassMid),
              mid_color(audio.mid), mid_high_color(audio.midHigh),
              high_color(audio.high), high_top_color(audio.highTop)]
        bar_width = size // 6

        for i in range(6):
            bar_height = int(round(levels[i] * (size - 2)))   # 0..1 level -> pixels
            left = i * bar_width + 2
            right = left + bar_width - 3
            if bar_height > 0:
                face[size - 1 - bar_height:size - 1, left:right] = colors[i]   # grows upward

        # White border that flashes on beats and fades out (beat_pulse goes 1 -> 0)
        flash = audio.beat_pulse
        for edge in (face[0, :], face[-1, :], face[:, 0], face[:, -1]):
            np.maximum(edge, flash, out=edge)

        # Give the face a quarter turn anticlockwise: bass ends up at the bottom, highTop
        # on top, and the bars grow out of the right-hand edge.
        face = np.rot90(face)

        # The same picture on all four faces, with faces 1 and 3 mirrored so their bars
        # grow out of the left-hand edge instead. The spectrum then spreads out from two
        # opposite edges of the cube, where face 0 meets face 1 and face 2 meets face 3.
        return self.layout.tile(face, mirror_alternate=True)
