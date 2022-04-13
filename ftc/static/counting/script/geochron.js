/* geochron v0.1 (c) 2014 Jiangping He */
$(window).load(function() {

    if (!grain_info) {
        return;
    }

    var mapZoom = 11;
    var myIcon = L.Icon.extend({
        options: {
            //iconUrl: "{% static 'counting/images/circle.png' %}",
            /* convert -size 81x81 xc:none -fill yellow -draw "circle 40,40 40,80" circle.png */
            iconSize: [6, 6],
            iconAnchor: [3, 3],
            popupAnchor: [0, 0]
        }
    });
    var normalIcon = new myIcon({
        iconUrl: iconUrl_normal
    });
    function makeDeleter(map, markers) {
        var rect = L.rectangle([
            [0., 0.],
            [0., 0.]
        ], {
            className: "ftc-rect-select-area",
            color: "#ff0000",
            fillOpacity: 0,
            stroke: true,
            weight: 2,
            fill: false,
            clickable: true
        });
        var selectedIcon = new myIcon({
            iconUrl: iconUrl_selected
        });
        var trash_mks_in = [];
        var oneCorner, twoCorner;
        var numClick = 0;
        function resetMarkers() {
            for (var i in trash_mks_in) {
                var indx = trash_mks_in[i]
                markers[indx].setIcon(normalIcon);
            }
            trash_mks_in = [];
        }
        function deleteSelected() {
            if (trash_mks_in.length !== 0) {
                var mks = {};
                for (var i in trash_mks_in) {
                    var indx = trash_mks_in[i]
                    mks[indx] = markers[indx];
                }
                undo.withUndo(removeFromMap(mks));
                trash_mks_in = [];
            }
        }
        function stopSelecting() {
            removeClass('ftc-btn-select', 'selecting');
            rect.setBounds([
                [0., 0.],
                [0., 0.]
            ]);
            resetMarkers();
        }
        function setDrawRectangle(e) {
            twoCorner = e.latlng;
            rect.setBounds([oneCorner, twoCorner]);
        }
        function setTwoCorner(e) {
            twoCorner = e.latlng;
            rect.setBounds([oneCorner, twoCorner]);
            bounds = L.latLngBounds(oneCorner, twoCorner);
            map.off('mousemove', setDrawRectangle);
            map._container.style.cursor = 'crosshair';
            var j = 0;
            for (var i in markers) {
                latlon = markers[i].getLatLng();
                if (bounds.contains(latlon)) {
                    trash_mks_in[j] = i;
                    markers[i].setIcon(selectedIcon);
                    j++;
                }
            }
            if (trash_mks_in.length > 0) {
                removeClass('ftc-btn-delete', 'leaflet-disabled');
            } else {
                trash_mks_in = [];
                restoreCounting(e);
            }
        }
        function setOneCorner(e) {
            //L.DomEvent.preventDefault(e);
            //L.DomEvent.stopPropagation(e);
            oneCorner = e.latlng;
            rect.setBounds([oneCorner, oneCorner]);
            rect.addTo(map).bringToFront();
            map.on('mousemove', setDrawRectangle);
        }
        function drawRectangle(e) {
            numClick++;
            if (numClick == 1) {
                setOneCorner(e);
            } else if (numClick == 2) {
                setTwoCorner(e);
            } else if (numClick == 3) {
                restoreCounting(e);
            } else {
                alert('click event should not listened any more');
            }
        }
        function restoreCounting(e) {
            L.DomEvent.preventDefault(e);
            L.DomEvent.stopPropagation(e);
            map.off('click', drawRectangle);
            map.on('click', onMapClick);
            numClick = 0;
            stopSelecting();
            addClass('ftc-btn-delete', 'leaflet-disabled');
        }
        return {
            deleteSelected: deleteSelected,
            restoreCounting: restoreCounting,
            drawRectangle: drawRectangle
        }
    }
    function makeMarkers(map) {
        var track_id = 0;
        var track_num = 0;
        var markers = {};
        return {
            makeDeleter: function() {
                return makeDeleter(map, markers);
            },
            // Returns a new track marker with a new track ID,
            // as an object with a single key (the new track ID)
            // with the value as this new marker. This return
            // value can be passed into addToMap as is.
            make: function(latlng) {
                var mk = new L.marker(latlng, {
                    icon: normalIcon,
                    riseOnHover: true,
                    className: 'jhe-fissionTrack-' + track_id
                }).on('click', function(e) {
                    //need this to prevent event propagation
                });
                var mks = {};
                mks[track_id] = mk;
                track_id++;
                return mks;
            },
            addToMap: function(markersToAdd) {
                for (var k in markersToAdd) {
                    mk = markersToAdd[k];
                    mk.setIcon(normalIcon);
                    mk.addTo(map);
                    markers[k] = mk;
                    track_num = track_num + 1;
                }
            },
            removeFromMap: function(markersToRemove) {
                for (var k in markersToRemove) {
                    map.removeLayer(markersToRemove[k]);
                    delete markers[k];
                    track_num = track_num - 1;
                }
            },
            removeAllFromMap: function() {
                var mks = {};
                for (var k in markers) {
                    mks[k] = markers[k];
                }
                removeFromMap(mks);
                return mks;
            },
            getLatLngs: function() {
                var latlngs = new Array();
                var j = 0;
                for (var i in markers) {
                    latlng = markers[i].getLatLng();
                    latlngs[j] = [latlng.lat, latlng.lng];
                    j++;
                }
                return latlngs;
            },
            trackCount: function() {
                return track_num;
            },
            empty: function() {
                for (var i in markers) {
                    return false;
                }
                return true;
            }
        };
    }
    var markers = null;
    var deleter = null;
    var markers = makeMarkers(map);
    var deleter = markers.makeDeleter();
    var buttons = {
        'homeView': {
            icon: 'fa-arrows-alt',
            tipText: 'fit images to window',
            action: function() {
                var yox = grain_info.image_height / grain_info.image_width;
                map.setView([yox / 2, 0.5], mapZoom);
            }
        },
        'undo': {
            icon: 'fa-history',
            tipText: 'undo',
            className_a: 'leaflet-disabled',
            action: function() {
                undo.undo();
            }
        },
        'redo': {
            icon: 'fa-repeat',
            tipText: 'redo',
            className_a: 'leaflet-disabled',
            action: function() {
                undo.redo();
            }
        },
        'select': {
            icon: 'fa-pencil-square-o',
            tipText: 'click twice to draw a rectangle and select multiple markers',
            action: function(e) {
                if (!hasClass('ftc-btn-select', 'selecting')) {
                    addClass('ftc-btn-select', 'selecting');
                    map.off('click', onMapClick);
                    map._container.style.cursor = 'crosshair';
                    map.on('click', deleter.drawRectangle);
                } else {
                    removeClass('ftc-btn-select', 'selecting');
                    deleter.restoreCounting(e);
                }
            }
        },
        'delete': {
            icon: 'fa-trash-o',
            tipText: 'delete selected fission track markers',
            className_a: 'leaflet-disabled',
            action: function(e) {
                deleter.deleteSelected();
                deleter.restoreCounting(e);
            }
        }
    };

    function makeUndoStack() {
        var undoStack = [];
        var redoStack = [];
        function execute(fromStack, toStack) {
            if (fromStack.length) {
                var f = fromStack.pop();
                toStack.push(f());
            }
        }
        function updateStackButton(stack, id) {
            if (stack.length) {
                removeClass(id, 'leaflet-disabled');
            } else {
                addClass(id, 'leaflet-disabled');
            }
        }
        function updateUndoRedoButtons() {
            updateStackButton(undoStack, 'ftc-btn-undo');
            updateStackButton(redoStack, 'ftc-btn-redo');
        }
        return {
            redo: function() {
                execute(redoStack, undoStack);
                updateUndoRedoButtons();
            },
            undo: function() {
                execute(undoStack, redoStack);
                updateUndoRedoButtons();
            },
            withUndo: function(f) {
                undoStack.push(f);
                redoStack = [];
                updateUndoRedoButtons();
            }
        };
    }
    var undo = makeUndoStack();

    function addClass(id, cls) {
        L.DomUtil.addClass(L.DomUtil.get(id), cls);
    }
    function removeClass(id, cls) {
        L.DomUtil.removeClass(L.DomUtil.get(id), cls);
    }
    function hasClass(id, cls) {
        L.DomUtil.hasClass(L.DomUtil.get(id), cls);
    }

    function updateTrackCounter() {
        $('#tracknum').val((1000 + markers.trackCount()).toString().slice(1));
    }

    function addToMap(markersToAdd) {
        markers.addToMap(markersToAdd);
        updateTrackCounter();
        return function() { return removeFromMap(markersToAdd); }
    }

    function removeFromMap(markersToRemove) {
        markers.removeFromMap(markersToRemove);
        updateTrackCounter();
        return function() { return addToMap(markersToRemove); }
    }

    function removeAllFromMap() {
        var deleted = markers.removeAllFromMap();
        updateTrackCounter();
        return function() { return addToMap(deleted); }
    }

    function createMarker(latlng) {
        var mks = markers.make(latlng);
        undo.withUndo(addToMap(mks));
    };

    function onMapClick(e) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);
        if (zStack.pointInRois(e.latlng.lat, e.latlng.lng)) {
            createMarker(e.latlng);
        }
    };

    function makeZStack(map, images, imageCount, yOverX, rois) {
        var bounds = [
            [0.0, 0.0],
            [yOverX, 1.0]
        ];
        var imageOverlayers = new Array();
        for (var i = 0; i < imageCount; i++) {
            imageOverlayers[i] = new L.imageOverlay(
                images[i], bounds
            ).addTo(map);
        }
        var currentLayer = 0;
        var polygon_arrays = rois;
        for (var i = 0; i < polygon_arrays.length; i++) {
            L.polygon(polygon_arrays[i], {
                color: 'white',
                opacity: 1.0,
                fill: false,
                clickable: true,
                className: 'ftc-rect-select-area'
            }).on('click', function(e) {
                L.DomEvent.preventDefault(e);
                L.DomEvent.stopPropagation(e);
            }).addTo(map);
        }
        function point_in_polygon(x, y, vs) {
            // ray-casting algorithm based on
            // http://www.ecse.rpi.edu/Homepages/wrf/Research/Short_Notes/pnpoly.html
            var inside = false;
            for (var i = 0, j = vs.length - 1; i < vs.length; j = i++) {
                var xi = vs[i][0],
                    yi = vs[i][1];
                var xj = vs[j][0],
                    yj = vs[j][1];
                var intersect = ((yi > y) != (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
                if (intersect) inside = !inside;
            }
            return inside;
        };
        function point_in_any_polygon(x, y, vss) {
            for (var i =0; i !== vss.length; ++i) {
                if (point_in_polygon(x, y, vss[i])) {
                    return true;
                }
            }
            return false;
        }
        function refresh() {
            imageOverlayers[currentLayer].bringToFront();
        }
        refresh();
        return {
            set: function(position) {
                currentLayer = position;
                refresh();
            },
            position: function() {
                return currentLayer;
            },
            decrement: function() {
                currentLayer = 0 < currentLayer? currentLayer - 1 : 0;
                refresh();
            },
            increment: function() {
                var c = currentLayer + 1;
                currentLayer = c < imageCount? c : imageCount - 1;
                refresh();
            },
            pointInRois: function(x, y) {
                return point_in_any_polygon(x, y, polygon_arrays);
            }
        };
    }

    var zStack = null;

    var map = L.map('map', {
        center: [grain_info.image_height / grain_info.image_width / 2, 0.5],
        zoom: mapZoom,
        minZoom: mapZoom - 2,
        maxZoom: mapZoom + 3,
        scrollWheelZoom: false
        //doubleClickZoom: false
    });
    map.attributionControl.setPrefix(''); // Don't show the 'Powered by Leaflet' text.
    buttonControl = L.easyButton(buttons, map, 'topright');
    buttonControl.getContainer().addEventListener('dblclick', function(e) {
        e.stopPropagation();
    });

    map.on('click', onMapClick)
        .on('dblclick', function(e) {
            $(this).data('jhe_double', 2);
        });

    /**************************
     *   wheel change layer   *
     **************************/
    $('#map').mousewheel(function(e, delta) {
        if (delta < 0) {
            zStack.dec();
        } else {
            zStack.inc();
        }
        sliders2.set(zStack.position());
        return false;
    });

    var UScale = L.Control.extend({
        options: {
            position: 'bottomleft',
            maxWidth: 100,
            imageWidthMeters: 1e-4,
        },

        onAdd: function (map) {
            map.on('move', this._update, this);
            map.whenReady(this._update, this);

            this.scale = document.createElement('div');
            this.scale.className = 'ftc-uscale-line-10';
            var container = document.createElement('div');
            container.className = 'ftc-uscale';
            container.appendChild(this.scale);  
            return container;
        },

        onRemove: function (map) {
            map.off('move', this._update, this);
        },

        _update: function () {
            if (!this.scale) {
                return;
            }
            var map = this._map;
            var y = map.getSize().y / 2;
            var maxLng =
                map.containerPointToLatLng([this.options.maxWidth, y]).lng -
                map.containerPointToLatLng([0, y]).lng;
            var maxMeters = this.options.imageWidthMeters * maxLng;
            this._updateMetric(maxMeters);
        },

        _updateMetric: function (maxMeters) {
            var unit = ' nm';
            var m = maxMeters / 1e-9;
            if (1000.0 <= m) {
                unit = ' \xB5m';
                m = maxMeters / 1e-6;
                if (1000.0 <= m) {
                    unit = ' mm';
                    m = maxMeters / 1e-3;
                }
            }
            var z = 1;
            while (10.0 <= m) {
                z *= 10;
                m /= 10.0;
            }
            var ratio = 1/m;
            var num = z;
            if (5.0 <= m) {
                num = 5 * z;
                ratio = 5/m;
                this.scale.className = 'ftc-uscale-line-5';
            } else if (2.0 <= m) {
                num = 2 * z;
                ratio = 2/m;
                this.scale.className = 'ftc-uscale-line-2';
            } else {
                this.scale.className = 'ftc-uscale-line-10';
            }
            this.scale.style.width = Math.round(this.options.maxWidth * ratio) + 'px';
            this.scale.innerHTML = num + unit;
        },
    });

    /**************************
     *   slider and tooltip   *
     **************************/
    var FocusControl = L.Control.extend({
        options: {
            position: 'topleft'
        },

        onAdd: function(map) {
            // create the control container with a particular class name
            var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control focus-slider-container');
            container.setAttribute('style', 'margin-left: 14px;margin-top: 27px;');
            this.slider_div = L.DomUtil.create('div', 'leaflet-bar-focus-slider', container);
            this.slider_div.id = 'focus-slider';
            this.slider_div.setAttribute('style', 'height:120px');
            return container;
        }
    });
    map.addControl(new FocusControl());

    if ('scale_x' in grain_info && grain_info.scale_x) {
        map.addControl(new UScale({
            position: 'bottomright',
            maxWidth: 300,
            imageWidthMeters: grain_info.scale_x * grain_info.image_width
        }));
    }

    var focusSliderElt = document.getElementById('focus-slider');
    var sliders2 = noUiSlider.create(focusSliderElt, {
        start: 0,
        orientation: 'vertical',
        range: {
            'min': 0,
            'max': 1
        },
        step: 1,
        format: {
            to: function(v) { return Math.floor(v); },
            from: function(v) { return Number(v); }
        },
        tooltips: [
            {
                to: function(x) { return Math.floor(x); }
            }
        ],
        keyboardDefaultStep: 1
    });

    sliders2.on('slide', function(ev) {
        zStack.set(sliders2.get());
    });

    focusSliderElt.onpointerdown = function(ev) {
        // Prevents the sample image from being dragged around
        // by movements that begin on the slider.
        ev.stopPropagation();
    };

    focusSliderElt.onclick = function(ev) {
        // Prevents points from being added
        // by movements that begin on the slider.
        ev.stopPropagation();
    };

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', atoken);
        }
    });

    var sliderNum = grain_info.images.length;
    sliders2.updateOptions({
        range: {
            'min': 0,
            'max': sliderNum - 1
        }
    }, true);
    var yox = grain_info.image_height / grain_info.image_width;
    zStack = makeZStack(map, grain_info.images, sliderNum, yox, grain_info.rois);
    markers = makeMarkers(map);
    deleter = markers.makeDeleter();
    if (('num_markers' in grain_info) && ('marker_latlngs' in grain_info)) {
        var latlng;
        for (var i = 0; i < grain_info.num_markers; i++) {
            latlng = grain_info.marker_latlngs[i];
            createMarker(latlng);
        }
    }
    map.setView([yox / 2, 0.5], mapZoom);
    updateTrackCounter();

    /* submit result */
    $('#tracknum-submit').click(function() {
        if (confirm("submit the result?") == true) {
            var latlngs = markers.getLatLngs();
            str = JSON.stringify({
                'counting_res': {
                    'proj_id': grain_info.proj_id,
                    'sample_id': grain_info.sample_id,
                    'grain_num': grain_info.grain_num,
                    'ft_type': grain_info.ft_type,
                    'image_width': grain_info.image_width,
                    'image_height': grain_info.image_height,
                    'marker_latlngs': latlng,
                    'track_num': markers.trackCount()
                }
            });
            $.ajax({
                url: updateTFNResult_url,
                type: 'POST',
                dataType: 'json',
                data: str,
                success: function(result) {
                    console.log('submitted: ' + result.reply);
                    window.location.href = getNewGrain_url;
                },
                error: function(xhr, errmsg, err) {
                    console.log(xhr.status + ": " + xhr.responseText);
                }
            });
        } else {
            console.log("You pressed Cancel!");
        }
    });

    $('#tracknum-save').click(function() {
        if (confirm("Save the intermedia result to the server?") == true) {
            var latlngs = markers.getLatLngs();
            str = JSON.stringify({
                'intermedia_res': {
                    'proj_id': grain_info.proj_id,
                    'sample_id': grain_info.sample_id,
                    'grain_num': grain_info.grain_num,
                    'ft_type': grain_info.ft_type,
                    'image_width': grain_info.image_width,
                    'image_height': grain_info.image_height,
                    'num_markers': latlngs.length,
                    'marker_latlngs': latlngs
                }
            });
            $.ajax({
                url: saveWorkingGrain_url,
                type: 'POST',
                dataType: 'json',
                data: str,
                success: function(result) {
                    console.log('submitted: ' + result.reply);
                },
                error: function(xhr, errmsg, err) {
                    console.log(xhr.status + ": " + xhr.responseText);
                    alert('Failed to save your intermedia result, Please try again.');
                }
            });

        }
    });
    $('#tracknum-restart').click(function(e) {
        if (confirm("Are you sure that you want to reset the counter for this grain?") == true) {
            if (!markers.empty()) {
                undo.withUndo(removeAllFromMap());
            }
            var yox = grain_info.image_height / grain_info.image_width;
            map.setView([yox / 2, 0.5], mapZoom);
        }
    });
})

