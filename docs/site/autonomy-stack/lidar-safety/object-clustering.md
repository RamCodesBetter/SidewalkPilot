# Object Clustering

The current runtime does not cluster LiDAR points into objects and does not classify obstacles.

`center_forward_distance()` filters valid returns and uses the nearest point inside one car-relative center corridor. This intentionally simple rule supports throttle limiting and emergency braking, but it cannot distinguish a person from a wall, estimate object width, or prove that empty adjacent space is traversable sidewalk.

Clustering could be researched later for telemetry or perception, but it must not weaken the nearest-return emergency rule or reintroduce steering based only on apparent LiDAR gaps.
