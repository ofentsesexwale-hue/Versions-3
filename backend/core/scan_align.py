"""Align a photographed page onto an official blank. Local OpenCV only."""
from __future__ import annotations

import math
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps


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
        return [scan]
    return [scan.rotate(90, expand=True), scan.rotate(270, expand=True)]


def order_points(pts):
    import numpy as np
    pts = np.array(pts, dtype='float32')
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    ordered = np.zeros((4, 2), dtype='float32')
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def crop_document(image):
    """Pull the paper out of an iPhone photo (desk, thumbs, background)."""
    if not opencv_available() or image is None:
        return image, False
    import cv2
    import numpy as np
    mat = _to_cv(image)
    h, w = mat.shape[:2]
    scale = 1100 / max(h, w)
    if scale > 1:
        scale = 1.0
    small = cv2.resize(mat, (max(1, int(w * scale)), max(1, int(h * scale))))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 40, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = small.shape[0] * small.shape[1]
    page = None
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:10]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.20 * area:
            page = approx.reshape(4, 2).astype('float32') / scale
            break
        # C02's photocopied grid approximates as 5–6 vertices, never 4.
        if 5 <= len(approx) <= 8 and cv2.contourArea(c) > 0.35 * area:
            rect = cv2.minAreaRect(c)
            page = cv2.boxPoints(rect).astype('float32') / scale
            break
    if page is None:
        return image, False
    pts = order_points(page)
    width_a = np.linalg.norm(pts[2] - pts[3])
    width_b = np.linalg.norm(pts[1] - pts[0])
    height_a = np.linalg.norm(pts[1] - pts[2])
    height_b = np.linalg.norm(pts[0] - pts[3])
    width = int(max(width_a, width_b))
    height = int(max(height_a, height_b))
    if width < 200 or height < 200:
        return image, False
    dest = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype='float32')
    matrix = cv2.getPerspectiveTransform(pts, dest)
    warped = cv2.warpPerspective(mat, matrix, (width, height), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    return _from_cv(warped), True


def match_blank(scan, blank):
    """Return (warped PIL or None, inliers, alignment_failed)."""
    if not opencv_available():
        return None, 0, True
    best = None
    for probe in maybe_rotate_to_template(scan, blank):
        warped, inliers, failed = _homography_to_blank(probe, blank)
        if failed or warped is None:
            continue
        bonus = _title_upright_bonus(warped)
        score = inliers + bonus
        if best is None or score > best[0]:
            best = (score, warped, inliers)
    if best:
        return best[1], best[2], False
    return _fit_page_to_blank(scan, blank)


def _title_upright_bonus(warped):
    """Prefer the 90° that still reads C01/C03 in the header, not sideways grid lines."""
    try:
        from .scan_engines import read_image
        w, h = warped.size
        top = warped.crop((0, 0, w, max(8, int(h * 0.22))))
        text = (read_image(top)[0] or '').upper()
    except Exception:
        return 0
    hits = 0
    for needle in (
        'C01', 'C02', 'C03', 'HOUSEHOLD', 'BENEFICIARY', 'ASSESSMENT',
        'INTAKE', 'CW 05', 'CW05', 'ADULT', 'CHILD',
    ):
        if needle in text:
            hits += 1
    return hits * 40


def _feature_homography(gray_s, gray_d, detector, norm, ratio=0.75):
    """Return (H on the shrunk greys, inlier count) or (None, matches_or_zero)."""
    import cv2
    import numpy as np
    k1, d1 = detector.detectAndCompute(gray_s, None)
    k2, d2 = detector.detectAndCompute(gray_d, None)
    if d1 is None or d2 is None or len(k1) < 12 or len(k2) < 12:
        return None, 0
    matcher = cv2.BFMatcher(norm, crossCheck=False)
    pairs = matcher.knnMatch(d1, d2, k=2)
    good = []
    for pair in pairs:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio * n.distance:
            good.append(m)
    if len(good) < 12:
        return None, len(good)
    src_pts = np.float32([k1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([k2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H_small, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H_small is None or mask is None:
        return None, 0
    return H_small, int(mask.sum())


def _homography_to_blank(scan, blank):
    import cv2
    import numpy as np
    src_full = _to_cv(scan)
    dst = _to_cv(blank)
    h, w = dst.shape[:2]

    def shrink(mat, target=880):
        hh, ww = mat.shape[:2]
        s = target / max(hh, ww)
        if s >= 1:
            return mat, 1.0
        return cv2.resize(mat, (int(ww * s), int(hh * s))), s

    src_s, ss = shrink(src_full)
    dst_s, ds = shrink(dst)
    gray_plain_s = cv2.cvtColor(src_s, cv2.COLOR_BGR2GRAY)
    gray_plain_d = cv2.cvtColor(dst_s, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_clahe_s = clahe.apply(gray_plain_s)
    gray_clahe_d = clahe.apply(gray_plain_d)
    qa = gray_plain_s.shape[1] / max(1, gray_plain_s.shape[0])
    ba = gray_plain_d.shape[1] / max(1, gray_plain_d.shape[0])
    if abs(math.log(qa / ba)) > math.log(1.65):
        return None, 0, True

    attempts = [
        ('orb', cv2.ORB_create(3500), cv2.NORM_HAMMING, 0.75, gray_clahe_s, gray_clahe_d),
        ('orb', cv2.ORB_create(3500), cv2.NORM_HAMMING, 0.75, gray_plain_s, gray_plain_d),
    ]
    if hasattr(cv2, 'SIFT_create'):
        attempts.append(
            ('sift', cv2.SIFT_create(nfeatures=4000), cv2.NORM_L2, 0.8, gray_plain_s, gray_plain_d)
        )

    orb_best = None
    sift_best = None
    for kind, detector, norm, ratio, gray_s, gray_d in attempts:
        H_small, inliers = _feature_homography(gray_s, gray_d, detector, norm, ratio=ratio)
        if H_small is None or inliers < 10:
            continue
        s_src = np.array([[ss, 0, 0], [0, ss, 0], [0, 0, 1]], dtype='float64')
        s_dst_inv = np.array([[1 / ds, 0, 0], [0, 1 / ds, 0], [0, 0, 1]], dtype='float64')
        H = s_dst_inv @ H_small @ s_src
        if not _homography_covers_page(H, src_full.shape, (h, w)):
            continue
        warped = cv2.warpPerspective(
            src_full, H, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255),
        )
        candidate = (inliers, _from_cv(warped))
        if kind == 'orb':
            if orb_best is None or inliers > orb_best[0]:
                orb_best = candidate
        else:
            if sift_best is None or inliers > sift_best[0]:
                sift_best = candidate
    # A solid ORB page match (C01 household) is geometrically tighter than a
    # higher-inlier SIFT warp that still covers the page but smears ticks.
    if orb_best and orb_best[0] >= 70:
        return orb_best[1], orb_best[0], False
    if sift_best and (orb_best is None or sift_best[0] > orb_best[0]):
        return sift_best[1], sift_best[0], False
    if orb_best:
        return orb_best[1], orb_best[0], False
    return None, 0, True


def _homography_covers_page(H, src_shape, dst_hw):
    """True when H maps the photo onto the blank, not onto one table cell.

    C02's grid produces high inlier counts for collapsed/bowtie warps. Those
    used to pass the corner-bounds check and be reported as C01 with 60 inliers.
    """
    import cv2
    import numpy as np
    h, w = dst_hw
    sh, sw = src_shape[:2]
    corners = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]]).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    xs, ys = projected[:, 0], projected[:, 1]
    if min(xs) < -0.45 * w or max(xs) > 1.45 * w or min(ys) < -0.45 * h or max(ys) > 1.45 * h:
        return False
    det = float(np.linalg.det(H[0:2, 0:2]))
    if det < 0.12 or det > 10:
        return False
    area = abs(cv2.contourArea(projected.astype(np.float32)))
    hull_area = abs(cv2.contourArea(cv2.convexHull(projected.astype(np.float32))))
    blank_area = float(w * h)
    if blank_area <= 0 or area < 0.25 * blank_area or area > 1.4 * blank_area:
        return False
    if hull_area > 0 and area / hull_area < 0.85:
        return False
    return True


def _fit_page_to_blank(scan, blank):
    """Last resort when feature matching cannot see past a repeating grid.

    Rotate to the blank's orientation and stretch. Only accepted when the
    header still reads as this form, so a C02 photo cannot land on C01.
    """
    best = None
    for probe in maybe_rotate_to_template(scan, blank):
        fitted = probe.resize(blank.size, Image.Resampling.LANCZOS)
        bonus = _title_upright_bonus(fitted)
        if bonus < 40:
            continue
        if best is None or bonus > best[0]:
            best = (bonus, fitted)
    if not best:
        return None, 0, True
    return best[1], 14, False



def identify_form_page(image, hint=None):
    """Which official blank this photo is (form code + page). Missing sheets are allowed."""
    from .official_blanks import BLANKS_DIR, load_meta
    if image is None or not opencv_available():
        return None, None, None, 0, True
    meta = load_meta()
    pages = meta.get('pages') or {}
    keys = list(pages.keys())
    if hint and hint != 'unknown':
        hinted = [k for k in keys if k.startswith(str(hint) + ':')]
        if hinted:
            keys = hinted
    best = None
    for key in keys:
        info = pages[key]
        code, idx = key.split(':')
        path = BLANKS_DIR / info['file']
        if not path.exists():
            continue
        blank = Image.open(path)
        for degrees in (0, 180):
            probe = image if degrees == 0 else image.rotate(180, expand=True)
            warped, inliers, failed = match_blank(probe, blank)
            if failed:
                continue
            bonus = _title_upright_bonus(warped)
            score = inliers + bonus
            if best is None or score > best[0]:
                best = (score, code, int(idx), warped, inliers)
    if not best or best[4] < 14:
        if hint and hint != 'unknown' and len(keys) < len(pages):
            return identify_form_page(image, hint=None)
        return None, None, None, (best[4] if best else 0), True
    return best[1], best[2], best[3], best[4], False


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


# A checkbox crop is framed on the printed box, so the outline sits in the
# outer band of the crop. Ink is only counted in the middle, which on a ~28px
# box leaves an 8px margin - wider than the alignment residual we measure.
CHECKBOX_INSET = 0.28
# Measured off the pristine blanks (no ink at all: every box scores 0.0000)
# and off the ticked/unticked crops in core/tests/fixtures/handwrite.
CHECKBOX_EMPTY_MAX = 0.06
CHECKBOX_TICKED_MIN = 0.12

TICK_EMPTY = 'empty'
TICK_MARKED = 'ticked'
TICK_UNREADABLE = 'unreadable'


def _paper_cutoff(gray):
    """Darkness below which a pixel is ink, judged against this box's own paper.

    Autocontrast cannot be used here: on a blank box it stretches the printed
    outline down to pure black and manufactures a tick out of nothing.
    """
    values = sorted(gray.getdata())
    if not values:
        return 0
    paper = values[min(len(values) - 1, int(len(values) * 0.85))]
    return max(40, int(paper * 0.6))


def _inset_region(gray, inset):
    width, height = gray.size
    mx, my = int(width * inset), int(height * inset)
    return gray.crop((mx, my, max(mx + 1, width - mx), max(my + 1, height - my)))


def ink_fill_ratio(crop, reference=None, inset=CHECKBOX_INSET):
    """Share of the box interior covered by ink the printed form does not have.

    Two things keep the form itself out of the measurement. The printed
    outline is excluded by only looking at an inset region, and when the
    matching page of the official blank is supplied, ink already present on
    the blank at that spot is discounted - so a box the atlas has landed on
    printed text cannot read as a tick either.
    """
    gray = crop.convert('L')
    cutoff = _paper_cutoff(gray)
    inner = _inset_region(gray, inset)
    pixels = list(inner.getdata())
    if not pixels:
        return 0.0
    if reference is None:
        return sum(1 for p in pixels if p < cutoff) / len(pixels)
    ref = reference.convert('L')
    if ref.size != gray.size:
        ref = ref.resize(gray.size, Image.Resampling.LANCZOS)
    # Grow the blank's ink by a pixel so a small alignment residual does not
    # leave a sliver of printed outline looking like a pen stroke.
    ref_inner = _inset_region(ref, inset).filter(ImageFilter.MinFilter(3))
    ref_cutoff = _paper_cutoff(ref)
    ref_pixels = list(ref_inner.getdata())
    added = sum(
        1 for p, r in zip(pixels, ref_pixels)
        if p < cutoff and r >= ref_cutoff
    )
    return added / len(pixels)


def checkbox_state(crop, reference=None):
    """Read one checkbox as ticked, empty, or too close to call.

    A blank box is safe and a wrong tick is not, so anything between the two
    thresholds is reported as unreadable rather than guessed.
    """
    ratio = ink_fill_ratio(crop, reference)
    if ratio >= CHECKBOX_TICKED_MIN:
        return TICK_MARKED, ratio
    if ratio <= CHECKBOX_EMPTY_MAX:
        return TICK_EMPTY, ratio
    return TICK_UNREADABLE, ratio


def crop_to_jpeg(crop, quality=70):
    buf = BytesIO()
    crop.convert('RGB').save(buf, format='JPEG', quality=quality)
    return buf.getvalue()
