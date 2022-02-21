/* geochron v0.1 (c) 2014 Jiangping He */
$(window).load(function() {

    if (!grain_info) {
        return;
    }

    var ftc_res = {};
    var overlayerImgUrl;
    var sliderNum;
    var imageBounds = [
        [0.0, 0.0],
        [1., 1.]
    ];

    var imageOverlayers = new Array();
    var mapView = [0.5, 0.5];
    var mapZoom = 11;
    var numClick = 0;
    var oneCorner, twoCorner;
    var track_id = 0;
    var track_num = 0;
    var markers = {};
    var polygon_arrays = new Array();
    var trash_mks_in = new Array();
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
    var selectedIcon = new myIcon({
        iconUrl: iconUrl_selected
    });
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
    var buttons = {
        'homeView': {
            icon: 'fa-arrows-alt',
            tipText: 'fit images to window',
            action: function() {
                map.setView(mapView, mapZoom);
            }
        },
        'undo': {
            icon: 'fa-history',
            tipText: 'undo',
            className_a: 'leaflet-disabled',
            action: function() {
                /*alert('hello! undo');*/
            }
        },
        'redo': {
            icon: 'fa-repeat',
            tipText: 'redo',
            className_a: 'leaflet-disabled',
            action: function() {
                /*alert('hello! redo');*/
            }
        },
        'select': {
            icon: 'fa-pencil-square-o',
            tipText: 'click twice to draw a rectangle and select multiple markers',
            action: function(e) {
                if (L.DomUtil.get($('#ftc-btn-select')).css('background-color')!='rgb(219, 219, 219)') {
                    //map.dragging.disable();
                    map.off('click', checkClick);
                    map._container.style.cursor = 'crosshair';
                    L.DomUtil.get($('#ftc-btn-select')).css('background-color', '#dbdbdb');
                    map.on('click', drawRectangle);
                } else {
                    //
                    for (i = trash_mks_in.length - 1; i >= 0; i--) {
                        indx = trash_mks_in[i]
                        markers[indx].setIcon(normalIcon);
                    }
                    trash_mks_in = [];
                    restoreCounting(e);
                }
            }
        },
        'delete': {
            icon: 'fa-trash-o',
            tipText: 'delete selected fission track markers',
            className_a: 'leaflet-disabled',
            action: function(e) {
                deleteSelected(e);
            }
        }
    };

    var getObjectSize = function(obj) {
        var len = 0,
            key;
        for (key in obj) {
            if (obj.hasOwnProperty(key)) len++;
        }
        return len;
    };
    //==========================
    function createMarker(latlng) {
        track_num = track_num + 1;
        $('#tracknum').val((1000 + track_num).toString().slice(1));
        var mk = new L.marker(latlng, {
                icon: normalIcon,
                riseOnHover: true,
                className: 'jhe-fissionTrack-' + track_id
            })
            .on('click', function(e) {
                //console.log("click");
                //need this to prevent event propagation
            })
            .addTo(map);
        markers[track_id] = mk;
        track_id++;
    };

    function onMapClick(e) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);
        //e.originalEvent.ctrlKey
        var p = e.latlng.toString();
        var pinp = false
        for (var i = 0; i < polygon_arrays.length; i++) {
            pinp = pinp || point_in_polygon([e.latlng.lat, e.latlng.lng],  polygon_arrays[i])
        }
        //console.log(e.latlng + ': ' + pinp);
        if (pinp) {
            createMarker(e.latlng);
        }
    };

    function deleteSelected(e) {
        if (!($.isEmptyObject(e.currentTarget))) {
            if (e.currentTarget.id == "ftc-btn-delete" && trash_mks_in.length > 0) {
                for (i = trash_mks_in.length - 1; i >= 0; i--) {
                    indx = trash_mks_in[i]
                    map.removeLayer(markers[indx]);
                    delete markers[indx];
                    track_num = track_num - 1;
                }
                $('#tracknum').val((1000 + track_num).toString().slice(1));
                console.log('after delete, marker #: ' + getObjectSize(markers));
                trash_mks_in = [];
            }
        }
        restoreCounting(e);
    }
    //
    function setDrawRectangle(e) {
        //L.DomEvent.preventDefault(e);
        //L.DomEvent.stopPropagation(e);
        twoCorner = e.latlng;
        rect.setBounds([oneCorner, twoCorner]);
    }

    function setTwoCorner(e) {
        twoCorner = e.latlng;
        rect.setBounds([oneCorner, twoCorner]);
        bounds = L.latLngBounds(oneCorner, twoCorner);
        //--L.DomUtil.get($('#ftc-btn-select')).css('background-color', '#fff');
        //L.DomEvent.preventDefault(e);
        //L.DomEvent.stopPropagation(e);
        //L.DomEvent.disableClickPropagation(e);
        map.off('mousemove', setDrawRectangle);
        //map.off('click', 'drawRectangle');
        //map.dragging.enable();
        map._container.style.cursor = 'crosshair';
        j = 0;
        for (i in markers) {
            latlon = markers[i].getLatLng();
            if (bounds.contains(latlon)) {
                trash_mks_in[j] = i;
                markers[i].setIcon(selectedIcon);
                j++;
            }
        }
        if (trash_mks_in.length > 0) {
            L.DomUtil.get($('#ftc-btn-delete')).removeClass('leaflet-disabled');
        } else {
            trash_mks_in = [];
            restoreCounting(e);
            console.log('no delete acton. marker #: ' + getObjectSize(markers));
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

    function restoreCounting(e) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);
        map.off('click', drawRectangle);
        map.on('click', checkClick);
        numClick = 0;
        L.DomUtil.get($('#ftc-btn-select')).css('background-color', '#fff');
        L.DomUtil.get($('#ftc-btn-delete')).addClass('leaflet-disabled');
        rect.setBounds([
            [0., 0.],
            [0., 0.]
        ]);
    }

    function drawRectangle(e) {
        numClick++;
        if (numClick == 1) {
            setOneCorner(e);
        } else if (numClick == 2) {
            setTwoCorner(e);
        } else if (numClick == 3) {
            for (i = trash_mks_in.length - 1; i >= 0; i--) {
                indx = trash_mks_in[i]
                markers[indx].setIcon(normalIcon);
            }
            trash_mks_in = [];
            restoreCounting(e);
        } else {
            alert('click event should not listened any more');
        }
    }

    function checkClick(e) {
        var that = this;
        setTimeout(function() {
            var double_btn = parseInt($(that).data('jhe_double'), 10);
            if (double_btn > 0) {
                $(that).data('jhe_double', double_btn - 1);
                return false;
            } else {
                onMapClick(e);
            }
        }, 300);
    }

    function point_in_polygon(point, vs) {
        // ray-casting algorithm based on
        // http://www.ecse.rpi.edu/Homepages/wrf/Research/Short_Notes/pnpoly.html
        var x = point[0],
            y = point[1];
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

    function slider_bringToFront(position) {
        imageOverlayers[position].bringToFront();
        var topImg = imageOverlayers[position]._image;
        var chldr = topImg.parentElement.children;
        var i = null;
        for (i = (chldr.length) - 1; i >= 0; i--) {
            /* reslt = chldr.item(i).getElementsByClassName('ftc-rect-select-area'); */
            if (chldr.item(i).tagName.toLowerCase() == "svg") {
                break;
            }
        }
        if (i !== null) {
            $(chldr.item(i)).insertAfter($(topImg));
        }
    };
    map = L.map('map', {
        center: mapView,
        zoom: mapZoom,
        minZoom: mapZoom - 2,
        maxZoom: mapZoom + 3,
        scrollWheelZoom: false
        //doubleClickZoom: false
        /* zoomControl: false */
    });
    map.attributionControl.setPrefix(''); // Don't show the 'Powered by Leaflet' text.
    map.setView(mapView, mapZoom);
    L.easyButton(buttons, map, 'topright');
    //L.easyButton(layersSlider, map, 'topleft');

    map.on('click', checkClick)
        .on('dblclick', function(e) {
            $(this).data('jhe_double', 2);
        });

    /**************************
     *   wheel change layer   *
     **************************/
    $('#map').mousewheel(function(e, delta) {
        var position = sliders2.get();
        position = position - delta;
        position = (position > (sliderNum - 1)) ? (sliderNum - 1) : ((position < 0) ? 0 : position);
        sliders2.set(position);
        slider_bringToFront(position);
        return false;
    });

    /**************************
     *   slider and tooltip   *
     **************************/
    var MyControl = L.Control.extend({
        options: {
            position: 'topleft'
        },

        onAdd: function(map) {
            // create the control container with a particular class name
            var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control slider2-container');
            container.setAttribute('style', 'margin-left: 14px;margin-top: 27px;');
            this.slider_div = L.DomUtil.create('div', 'leaflet-bar-slider2', container);
            this.slider_div.id = 'slider2';
            this.slider_div.setAttribute('style', 'height:120px');
            return container;
        }
    });

    map.addControl(new MyControl());

    var slider2elt = document.getElementById('slider2');
    var sliders2 = noUiSlider.create(slider2elt, {
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
        slider_bringToFront(sliders2.get());
    });

    slider2elt.onpointerdown = function(ev) {
        // Prevents the sample image from being dragged around
        // by movements that begin on the slider.
        ev.stopPropagation();
    };

    slider2elt.onclick = function(ev) {
        // Prevents points from being added
        // by movements that begin on the slider.
        ev.stopPropagation();
    };

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', atoken);
        }
    });

    ftc_res['proj_id'] = grain_info.proj_id;
    ftc_res['sample_id'] = grain_info.sample_id;
    ftc_res['grain_num'] = grain_info.grain_num;
    ftc_res['ft_type'] = grain_info.ft_type;
    ftc_res['image_width'] = grain_info.image_width;
    ftc_res['image_height'] = grain_info.image_height;
    console.log(grain_info.proj_id + ', ' + grain_info.sample_id + ', ' + grain_info.grain_num + ', ' + grain_info.ft_type);
    var yox = grain_info.image_height / grain_info.image_width;
    imageBounds[1] = [yox, 1.0];
    mapView = [yox / 2, 0.5];
    overlayerImgUrl = grain_info.images;
    sliderNum = overlayerImgUrl.length;
    sliders2.updateOptions({
        range: {
            'min': 0,
            'max': sliderNum - 1
        }
    }, true);
    for (var i = 0; i < sliderNum; i++) {
        imageOverlayers[i] = new L.imageOverlay(overlayerImgUrl[i], imageBounds).addTo(map);
    }
    imageOverlayers[0].bringToFront();
    if (('num_markers' in grain_info) && ('marker_latlngs' in grain_info)) {
        var latlng;
        for (var i = 0; i < grain_info.num_markers; i++) {
            latlng = grain_info.marker_latlngs[i];
            createMarker(latlng);
        }
    }
    polygon_arrays = grain_info.rois;
    for (var i = 0; i < polygon_arrays.length; i++) {
        polygon_array = polygon_arrays[i]
        L.polygon(polygon_array, {
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
    map.setView(mapView, mapZoom);

    /* submit result */
    $('#tracknum-submit').click(function() {
        if (confirm("submit the result?") == true) {
            ftc_res['track_num'] = track_num;
            latlngs = new Array();
            var j = 0;
            for (var i in markers) {
                latlng = markers[i].getLatLng();
                latlngs[j] = [latlng.lat, latlng.lng];
                j++;
            }
            ftc_res['marker_latlngs'] = latlngs
            str = JSON.stringify({
                'counting_res': ftc_res
            });
            $.ajax({
                url: updateTFNResult_url,
                type: 'POST',
                dataType: 'json',
                data: str,
                success: function(result) {
                    console.log('submitted: ' + result.reply);
                    ftc_res = {};
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
            latlngs = new Array();
            var j = 0;
            for (var i in markers) {
                latlng = markers[i].getLatLng();
                latlngs[j] = [latlng.lat, latlng.lng];
                j++;
            }
            // use ftc_res info
            res = {
                'proj_id': ftc_res['proj_id'],
                'sample_id': ftc_res['sample_id'],
                'grain_num': ftc_res['grain_num'],
                'ft_type': ftc_res['ft_type'],
                'image_width': ftc_res['image_width'],
                'image_height': ftc_res['image_height'],
                'num_markers': j,
                'marker_latlngs': latlngs
            };
            str = JSON.stringify({
                'intermedia_res': res
            });
            console.log('total markers: ' + j);
            console.log(latlngs);
            console.log(str);
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
    $('#tracknum-restart').click(function() {
        if (confirm("Are you sure that you want to reset the counter for this grain?") == true) {
            track_num = 0;
            for (var i in markers) {
                map.removeLayer(markers[i]);
            }
            markers = {};
            $('#tracknum').val((1000 + track_num).toString().slice(1));
            map.setView(mapView, mapZoom);
        }
    });

    // end  
})

