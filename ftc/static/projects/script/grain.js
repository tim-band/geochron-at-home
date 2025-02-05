function forEach(arr, f) {
    for (var i = 0; i !== arr.length; ++i) {
        f(arr[i], i);
    }
}

function forEachInCycle(arr, f) {
    var lastI = arr.length - 1;
    var lastV = arr[lastI];
    forEach(arr, function(v, i) {
        f(lastV, v, lastI, i);
        lastV = v;
        lastI = i;
    });
}

function pointsClose(a, b, closeness) {
    return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y)) < closeness;
}

// returns the point on the (extended) line start-end closest to the
// point pt, provided that it is less than closeness away from the
// extended line.
function closePointOnLine(pt, start, end, closeness) {
    // vector of line
    var vx = end.y - start.y;
    var vy = end.x - start.x;
    // pt relative to start of line
    var px = pt.y - start.y;
    var py = pt.x - start.x;
    // p dot v
    var pv = px * vx + py * vy;
    // |v| squared
    var v2 = vx * vx + vy * vy;
    // closest point is how far along v?
    var prop = pv / v2;
    // which is which point?
    var i = {
        x: start.x + prop * vx,
        y: start.y + prop * vy
    };
    if (pointsClose(i, pt, closeness)) {
        return i;
    }
    return null;
}

// lines are as + at*ad and bs + bt*bd (at,bt <- [0,1])
// so at the crossing point: as + at*ad = bs +bt*bd
// separating out co-ordinates (0 and 1 for x and y):
// as0 + at*ad0 = bs0 + bt*bd0
// as1 + at*ad1 = bs1 + bt*bd1
// multiply through by bd1 and bd0
// as0*bd1 + at*ad0*bd1 = bs0*bd1 + bt*bd0*bd1
// as1*bd0 + at*ad1*bd0 = bs1*bd0 + bt*bd1*bd0
// subtracting:
// as0*bd1 - as1*bd0 + at*(ad0*bd1 - ad1*bd0) = bs0*bd1 - bs1*bd0
// `at` on the LHS:
// at*(ad0*bd1 - ad1*bd0) = bs0*bd1 - bs1*bd0 - as0*bd1 + as1*bd0
// at*(ad0*bd1 - ad1*bd0) = bd1 * (bs0 - as0) + bd0 * (as1 - bs1)
// by symmetry a/b:
// bt*(bd0*ad1 - bd1*ad0) = ad1 * (as0 - bs0) + ad0 * (bs1 - as1)
// re-arranging to look like the `a` version:
// bt*(ad0*bd1 - ad1*bd0) = ad1 * (bs0 - as0) + ad0 * (as1 - bs1)
function linesCross(aStart, aEnd, bStart, bEnd) {
    var ad = [aEnd[0] - aStart[0], aEnd[1] - aStart[1]];
    var bd = [bEnd[0] - bStart[0], bEnd[1] - bStart[1]];
    var max = ad[0] * bd[1] - ad[1] * bd[0];
    var min = 0;
    if (max < 0) {
        min = max;
        max = 0;
    }
    var sd0 = bStart[0] - aStart[0];
    var sd1 = aStart[1] - bStart[1];
    var b = bd[1] * sd0 + bd[0] * sd1;
    if (b < min || max < b) {
        return false;
    }
    var a = ad[1] * sd0 + ad[0] * sd1;
    return min <= a && a <= max;
}

function noop() { }

function wantsToMerge(crystal, v, i, region) {
    if (region.length < 2) {
        return false;
    }
    var lasti = i === 0? region.length - 1 : i - 1;
    var nexti = i === region.length - 1? 0 : i + 1;
    var lastp = crystal.map.latLngToLayerPoint(region[lasti]);
    var nextp = crystal.map.latLngToLayerPoint(region[nexti]);
    var p = crystal.map.latLngToLayerPoint(v);
    return pointsClose(p, lastp, 10) || pointsClose(p, nextp, 10);
}

function mergePoints(crystal, i, region, region_index) {
    if (region.length === 2 && 1 < crystal.region_points.length) {
        // gone down to a single point. If there are more regions,
        // just delete the whole region.
        return crystal.region_points.slice(0, region_index).concat(
            crystal.region_points.slice(region_index + 1));
    }
    var r = region.slice(0, i).concat(region.slice(i + 1));
    var new_regions = crystal.region_points.slice(0, region_index).concat(
        [r], crystal.region_points.slice(region_index + 1));
    return new_regions;
}

// get a list of sides that cross other sides, sorted by
// their lengths
function getSplits(i, region) {
    var n = region.length;
    if (n < 5) {
        return [];
    }
    // moving sides are i0->i and i->i1
    var i0 = (i + n - 1) % n; // node before i
    var i1 = (i + 1) % n; // node after i
    var cuts = {};
    // iterate through the other non-adjacent sides
    var prev = (i1 + 1) % n;
    for (var j = (prev + 1) % n; j !== i0; prev=j,j=(j+1)%n) {
        if (linesCross(region[i], region[i1], region[prev], region[j])) {
            cuts[i1] = true;
            cuts[j] = true;
        }
        if (linesCross(region[i0], region[i], region[prev], region[j])) {
            cuts[i] = true;
            cuts[j] = true;
        }
    }
    var c = Object.keys(cuts);
    c.sort();
    return c;
}

// get a list of sides in other_region that are crossed by the
// two sides next to node i from home_region
function getSplits2(i, home_region, other_region) {
    var m = home_region.length;
    var n = other_region.length;
    // moving sides are i0->i and i->i1
    var i0 = (i + m - 1) % m; // node before i
    var i1 = (i + 1) % m; // node after i
    var cuts = {};
    var prev = n-1;
    for (var j = 0; j !== n; prev=j, j++) {
        if (linesCross(home_region[i], home_region[i1], other_region[prev], other_region[j])) {
            cuts[j] = true;
        }
        if (linesCross(home_region[i0], home_region[i], other_region[prev], other_region[j])) {
            cuts[j] = true;
        }
    }
    var c = Object.keys(cuts);
    c.sort();
    return c;
}

// return the two biggest parts after slicing before each node
// index in the `splits` array (returns the biggest first, returns
// only one if there is only one part)
function getParts(splits, region, min_parts) {
    if (splits.length < min_parts) {
        return null;
    }
    var lastIndex = splits[splits.length - 1];
    var prev = splits[0];
    var parts = [region.slice(lastIndex).concat(region.slice(0, prev))];
    for (var j = 1, cur=splits[1]; j !== splits.length; prev=cur, ++j, cur=splits[j]) {
        parts.push(region.slice(prev, cur));
    }
    if (parts.length < min_parts) {
        return null;
    }
    parts.sort(function(a,b) {
        return b.length - a.length;
    });
    return parts.slice(0,2);
}

function mergeRegion(home_region, i, other_region) {
    var ps = getParts(getSplits2(i, home_region, other_region), other_region, 1);
    if (!ps) {
        return null;
    }
    return home_region.slice(0, i).concat(
        ps[0],
        home_region.slice(i + 1)
    );
}

function mergeRegions(regions, region_index, region, i) {
    for (var oi = 0; oi !== region_index; ++oi) {
        var other_region = regions[oi];
        var new_region = mergeRegion(region, i, other_region);
        if (new_region) {
            return regions.slice(0, oi).concat(
                [new_region],
                regions.slice(oi + 1, region_index),
                regions.slice(region_index + 1)
            );
        }
    }
    for (var oi = region_index + 1; oi < regions.length; ++oi) {
        var other_region = regions[oi];
        var new_region = mergeRegion(region, i, other_region);
        if (new_region) {
            return regions.slice(0, region_index).concat(
                regions.slice(region_index + 1, oi),
                [new_region],
                regions.slice(oi + 1)
            );
        }
    }
    return regions;
}

function reconfigureRegions(regions, region_index, region, i) {
    var parts = getParts(getSplits(i, region), region, 2);
    if (parts) {
        return regions.slice(0, region_index).concat(
            parts,
            regions.slice(region_index + 1)
        );
    }
    return mergeRegions(regions, region_index, region, i);
}

function moveMarker(ev, crystal, v, i, region, region_index) {
    v[0] = ev.latlng.lat;
    v[1] = ev.latlng.lng;
    var new_regions;
    if (wantsToMerge(crystal, v, i, region)) {
        new_regions = mergePoints(crystal, i, region, region_index);
    } else {
        new_regions = reconfigureRegions(crystal.region_points, region_index, region, i);
    }
    crystal.region_layer.setLatLngs(new_regions);
    return new_regions;
}

function moveShift(ev, crystal) {
    var dlat = ev.latlng.lat - ev.oldLatLng.lat - crystal.shift_y / crystal.image_width;
    var dlng = ev.latlng.lng - ev.oldLatLng.lng + crystal.shift_x / crystal.image_width;
    var new_regions = [];
    forEach(crystal.region_points, function(region) {
        var new_region = [];
        forEach(region, function(v) {
            new_region.push([v[0] + dlat, v[1] + dlng]);
        });
        new_regions.push(new_region);
    });
    crystal.region_layer.setLatLngs(new_regions);
    return [dlat, dlng];
}

/**
 * Returns normalized array of regions. This will remove repeated vertices
 * within the same region, exclude regions with fewer than three (unique)
 * vertices and reverse all anticlockwise regions. If no regions remain,
 * will return a default square.
 * @param {Array<Array<Array<number>>>} regions Array of regions, each of
 * which is an array of vertices, each of which is [lat,lng]
 * @returns 
 */
function normalizeRegions(regions) {
    var count = 0;
    forEach(regions, function(region, i) {
        if (2 < region.length) {
            var area = 0;
            var last = region[region.length - 1];
            var r = [];
            forEach(region, function(v) {
                if (v[0] !== last[0] || v[1] !== last[1]) {
                    area += v[0] * last[1] - last[0] * v[1];
                    r.push(v);
                    ++count;
                    last = v;
                }
            });
            if (r.length === 0) {
                // all the points were the same!
                r = [region[0]];
            }
            if (area < 0) {
                r.reverse();
            }
            regions[i] = r;
        } else {
            count += region.length;
        }
    });
    if (count === 0) {
        // Make a default square
        regions = [[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]];
    }
    return regions;
}

/**
 * Finds the (collective) centroid of an array of polygons
 * @param {number[][][]} regions Regions to
 * find the collective centroid of
 * @returns LatLng representing the centroid
 */
function getCentroid(regions) {
    var lat = 0;
    var lng = 0;
    var total_area = 0;
    forEach(regions, function(region) {
        var last = region[region.length - 1];
        forEach(region, function(v) {
            var area = v[0] * last[1] - last[0] * v[1];
            lat += area * (v[0] + last[0]) / 3;
            lng += area * (v[1] + last[1]) / 3;
            total_area += area;
            last = v;
        });
    });
    return L.latLng(lat / total_area, lng / total_area);
}

function removeRegionMarkers(crystal) {
    crystal.marker_layer.clearLayers();
    crystal.mid_marker_layer.clearLayers();
}

function addRegionMarkers(crystal) {
    var midIcon = L.icon({
        iconUrl: static_ring_svg_url,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
        className: 'region-mid-marker',
    });
    var vertexIcon = L.icon({
        iconUrl: static_pin_url,
        iconRetinaUrl: static_pin_url_2x,
        iconSize: [25, 41],
        iconAnchor: [13, 41],
        className: 'region-vertex-marker',
    });
    crystal.region_points = normalizeRegions(crystal.region_points);
    var new_regions;
    forEach(crystal.region_points, function(region, region_index) {
        forEach(region, function(vertex, index) {
            var v = L.marker(vertex, {
                draggable: true,
                icon: vertexIcon,
            }).addTo(crystal.marker_layer);
            L.DomEvent.on(v, 'dragstart', function() {
                crystal.mid_marker_layer.clearLayers();
            });
            L.DomEvent.on(v, 'drag', function(ev) {
                new_regions = moveMarker(ev, crystal, vertex, index, region, region_index);
            });
            L.DomEvent.on(v, 'dragend', function() {
                crystal.region_points = new_regions;
                removeRegionMarkers(crystal);
                addRegionMarkers(crystal);
            });
        });
        forEachInCycle(region, function(v0, v1, i0, i1) {
            var v = [ (v0[0] + v1[0])/2, (v0[1] + v1[1])/2 ];
            var m = L.marker(v, {
                draggable: true,
                icon: midIcon,
            }).addTo(crystal.mid_marker_layer);
            L.DomEvent.on(m, 'dragstart', function() {
                region.splice(i1, 0, v);
            });
            L.DomEvent.on(m, 'drag', function(ev) {
                new_regions = moveMarker(ev, crystal, v, i1, region, region_index);
            });
            L.DomEvent.on(m, 'dragend', function() {
                crystal.region_points = new_regions;
                removeRegionMarkers(crystal);
                addRegionMarkers(crystal);
            });
        });
    });
}

function disable_element(id) {
    var e = document.getElementById(id);
    if (e) {
        e.setAttribute('disabled', true);
    }
}

function enable_element(id) {
    var e = document.getElementById(id);
    if (e) {
        e.removeAttribute('disabled');
    }
}

function cancelEdit(crystal) {
    removeRegionMarkers(crystal);
    enable_element('edit');
    enable_element('edit_shift');
    disable_element('save');
    disable_element('save_shift');
    disable_element('cancel_edit');
    crystal.marker_layer.clearLayers();
}

function beginEdit(crystal) {
    removeRegionMarkers(crystal);
    crystal.region_points = normalizeRegions(crystal.region_points);
    crystal.region_layer.setLatLngs(crystal.region_points);
    addRegionMarkers(crystal);
    disable_element('edit');
    enable_element('save');
    enable_element('cancel_edit');
}

function save(crystal, url, form, error_callback) {
    const xhr = new XMLHttpRequest();
    const fd = new FormData(form);
    forEach(crystal.region_points, function(region, ri) {
        forEach(region, function(v, vi) {
            fd.append('vertex_' + ri + '_' + vi + '_x', v[1]);
            fd.append('vertex_' + ri + '_' + vi + '_y', v[0]);
        });
    });
    xhr.addEventListener("load", function() {
        cancelEdit(crystal);
    });
    if (error_callback) {
        xhr.addEventListener("error", function() {
            error_callback();
        });
    }
    xhr.open("POST", url);
    xhr.send(fd);
}

function beginShiftEdit(crystal) {
    var vertexIcon = L.icon({
        iconUrl: static_pin_url,
        iconRetinaUrl: static_pin_url_2x,
        iconSize: [25, 41],
        iconAnchor: [13, 41],
        className: 'region-vertex-marker',
    });
    var centroid = getCentroid(crystal.region_points);
    centroid.lat -= crystal.shift_y / crystal.image_width;
    centroid.lng += crystal.shift_x / crystal.image_width;
    var v = L.marker(centroid, {
        draggable: true,
        icon: vertexIcon,
    }).addTo(crystal.marker_layer);
    var shift_to;
    L.DomEvent.on(v, 'drag', function(ev) {
        shift_to = moveShift(ev, crystal);
    });
    L.DomEvent.on(v, 'dragend', function() {
        crystal.shift_x = shift_to[1] * crystal.image_width;
        crystal.shift_y = -shift_to[0] * crystal.image_width;
    });
    disable_element('edit_shift');
    enable_element('save_shift');
    enable_element('cancel_edit');
}

function saveShift(crystal, url, form, error_callback) {
    const xhr = new XMLHttpRequest();
    const fd = new FormData(form);
    fd.append('x', Math.floor(crystal.shift_x + 0.5));
    fd.append('y', Math.floor(crystal.shift_y + 0.5));
    xhr.addEventListener("load", function() {
        cancelEdit(crystal);
    });
    if (error_callback) {
        xhr.addEventListener("error", function() {
            error_callback();
        });
    }
    xhr.open("POST", url);
    xhr.send(fd);
}
