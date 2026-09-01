"""Align a photographed page onto an official blank. Local OpenCV only."""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps


def opencv_available():
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def _to_cv(image):
    import cv2
    import numpy as np
    rgb = ImageOps.exif_transpose(image).convert('RGB')
    return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)


def _from_cv(mat):
    import cv2
    rgb = cv2.cvtColor(mat, cv2.COLOR_BGR2RGB)
    from PIL import Image as PILImage
    return PILImage.fromarray(rgb)


def deskew_and_contrast(image):
    image = ImageOps.exif_transpose(image).convert('RGB')
    if not opencv_available():
        return ImageOps.autocontrast(image), False
    import cv2
    import numpy as np
    mat = _to_cv(image)
    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(gray > 0))
    rotated = False
    if len(coords) > 20:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 0.4 and abs(angle) < 15:
            h, w = mat.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            mat = cv2.warpAffine(mat, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
            rotated = True
    lab = cv2.cvtColor(mat, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    mat = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    return _from_cv(mat), rotated


def maybe_rotate_to_template(scan, blank):
    """Rotate scan 90° steps so landscape/portrait matches the blank."""
    sw, sh = scan.size
    bw, bh = blank.size
    blank_land = bw > bh
    scan_land = sw > sh
    if blank_land == scan_land:
        return scan
    return scan.rotate(90, expand=True)


def match_blank(scan, blank):
    """Return (warped PIL or None, inliers, alignment_failed)."""
    if not opencv_available():
        return None, 0, True
    import cv2
    import numpy as np
    scan = maybe_rotate_to_template(scan, blank)
    src = _to_cv(scan)
    dst = _to_cv(blank)
    h, w = dst.shape[:2]
    gray_s = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    gray_d = cv2.cvtColor(dst, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(4000)
    k1, d1 = orb.detectAndCompute(gray_s, None)
    k2, d2 = orb.detectAndCompute(gray_d, None)
    if d1 is None or d2 is None or len(k1) < 12 or len(k2) < 12:
        return None, 0, True
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = bf.knnMatch(d1, d2, k=2)
    good = []
    for pair in pairs:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.75 * n.distance:
            good.append(m)
    if len(good) < 12:
        return None, len(good), True
    src_pts = np.float32([k1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([k2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H is None or mask is None:
        return None, 0, True
    inliers = int(mask.sum())
    corners = np.float32([[0, 0], [src.shape[1], 0], [src.shape[1], src.shape[0]], [0, src.shape[0]]]).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, H)
    xs = projected[:, 0, 0]
    ys = projected[:, 0, 1]
    if inliers < 10:
        return None, inliers, True
    if min(xs) < -0.4 * w or max(xs) > 1.4 * w or min(ys) < -0.4 * h or max(ys) > 1.4 * h:
        return None, inliers, True
    det = float(np.linalg.det(H[0:2, 0:2]))
    if det < 0.15 or det > 8:
        return None, inliers, True
    warped = cv2.warpPerspective(src, H, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    return _from_cv(warped), inliers, False


def crop_box(image, box):
    x0, y0, x1, y1 = box
    w, h = image.size
    left = max(0, int(x0 * w))
    top = max(0, int(y0 * h))
    right = min(w, int(x1 * w))
    bottom = min(h, int(y1 * h))
    if right <= left or bottom <= top:
        return image.crop((0, 0, 1, 1))
    return image.crop((left, top, right, bottom))


def ink_fill_ratio(crop):
    gray = ImageOps.autocontrast(crop.convert('L'))
    pixels = list(gray.getdata())
    if not pixels:
        return 0.0
    dark = sum(1 for p in pixels if p < 140)
    return dark / len(pixels)


def crop_to_jpeg(crop, quality=70):
    buf = BytesIO()
    crop.convert('RGB').save(buf, format='JPEG', quality=quality)
    return buf.getvalue()
