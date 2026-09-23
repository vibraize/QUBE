"""
layout.py - the cube as one long canvas, plus helpers for individual faces.

    canvas x:  0 ....... 39 | 40 ...... 79 | 80 ..... 119 | 120 .... 159
               face 0       | face 1       | face 2       | face 3

Visual modes draw on the full strip, an array of shape (height, width, 3).
Something that runs off the right edge of face 3 continues on face 0, just like
walking around the cube.
"""
import numpy as np


class CubeLayout:
    def __init__(self, face_size, num_faces):
        self.face = face_size                  # pixels per side of one face
        self.faces = num_faces                 # number of faces
        self.width = face_size * num_faces     # full strip width
        self.height = face_size                # full strip height

    def new_canvas(self):
        """A black canvas for the whole cube: shape (height, width, 3)."""
        return np.zeros((self.height, self.width, 3), dtype=np.float32)

    def new_face(self):
        """A black canvas for a single face: shape (face, face, 3)."""
        return np.zeros((self.face, self.face, 3), dtype=np.float32)

    def face_view(self, canvas, i):
        """The slice of the canvas that belongs to face i.
        It is a view, so drawing on it draws on the canvas."""
        x0 = i * self.face
        return canvas[:, x0:x0 + self.face]

    def tile(self, face_img, mirror_alternate=False):
        """Copy one face image onto every face.
        mirror_alternate=True flips faces 1 and 3 left/right, so neighboring
        faces meet in a mirror line and the corners look seamless."""
        out = np.empty((self.height, self.width, 3), dtype=np.float32)
        for i in range(self.faces):
            if mirror_alternate and i % 2 == 1:
                self.face_view(out, i)[:] = face_img[:, ::-1]
            else:
                self.face_view(out, i)[:] = face_img
        return out

    def face_grid(self):
        """Coordinates for every pixel of one face, centered and scaled to -1..1.
        Returns (x, y, radius, angle), each shaped (face, face). y grows downward."""
        c = (np.arange(self.face, dtype=np.float32) + 0.5) / self.face * 2.0 - 1.0
        x, y = np.meshgrid(c, c)
        radius = np.sqrt(x * x + y * y)
        angle = np.arctan2(y, x)
        return x, y, radius, angle

    def strip_grid(self):
        """Coordinates for the whole strip: u goes 0..1 around the cube (and wraps),
        v goes 0..1 from top to bottom. Each shaped (height, width)."""
        u = (np.arange(self.width, dtype=np.float32) + 0.5) / self.width
        v = (np.arange(self.height, dtype=np.float32) + 0.5) / self.height
        return np.meshgrid(u, v)


def orient_for_panels(frame, layout, order, rotation, mirror):
    """Rearrange, mirror and rotate faces to match how the panels are mounted.
    Used by display code only. Mirror is applied first, then rotation."""
    identity = (list(order) == list(range(layout.faces))
                and not any(rotation) and not any(mirror))
    if identity:
        return frame
    f = layout.face
    out = np.empty_like(frame)
    for panel in range(layout.faces):
        src = order[panel]
        img = frame[:, src * f:(src + 1) * f]
        if mirror[panel]:
            img = img[:, ::-1]
        turns = (rotation[panel] // 90) % 4
        if turns:
            img = np.rot90(img, k=-turns)   # negative k = clockwise
        out[:, panel * f:(panel + 1) * f] = img
    return out
