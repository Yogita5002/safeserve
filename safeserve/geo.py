"""Distance and travel-time helpers."""
import math
import numpy as np
from . import config as C


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two (lat, lon) points."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(a, b):
    """Approximate road distance: haversine x circuity factor. a, b are (lat, lon)."""
    return haversine_km(a[0], a[1], b[0], b[1]) * C.CIRCUITY


def travel_min(a, b):
    """Travel time in minutes between two points at the configured speed."""
    return road_km(a, b) / C.SPEED_KMPH * 60.0


def time_matrix(points):
    """Integer minute matrix for a list of (lat, lon) points (used by OR-Tools)."""
    n = len(points)
    m = np.zeros((n, n), dtype=int)
    for i in range(n):
        for j in range(n):
            if i != j:
                m[i, j] = int(math.ceil(travel_min(points[i], points[j])))
    return m
