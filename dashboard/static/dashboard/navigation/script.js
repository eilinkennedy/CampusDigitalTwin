// initialize map
const defaultCenter = [9.7270, 76.7260];
const map = L.map("map").setView(defaultCenter, 17);

// base map
L.tileLayer(
"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
{
attribution:"&copy; OpenStreetMap",
referrerPolicy:"origin"
}).addTo(map);

function removeYouAreHereLayer(layer){
if(!layer || typeof layer.getPopup !== "function") return;
const popup = layer.getPopup();
if(!popup || typeof popup.getContent !== "function") return;
const content = String(popup.getContent());
if(content.includes("You are here")){
map.removeLayer(layer);
}
}

map.on("layeradd", function(e){
removeYouAreHereLayer(e.layer);
});

setTimeout(function(){
map.eachLayer(function(layer){
removeYouAreHereLayer(layer);
});
}, 0);

// draw shortest route (blue)
let routeLayer = null;

if(routeCoords.length > 1){

const route = routeCoords.map(p => [p.lat,p.lng]);

routeLayer = L.polyline(route,{
color:"blue",
weight:6
}).addTo(map);

// start marker
L.marker(route[0]).addTo(map)
.bindPopup("Start");

// destination marker
L.marker(route[route.length-1]).addTo(map)
.bindPopup("Destination");

// zoom to route
map.fitBounds(routeLayer.getBounds(),{
padding:[40,40]
});

}

// draw campus path graph (green/grey)
if(Array.isArray(campusPaths) && campusPaths.length > 0){
const campusGraphLayer = L.layerGroup().addTo(map);
const nodeIndex = new Set();
const graphBounds = [];

const edgeStyle = {
color:"#1f8f6a",
weight:3,
opacity:0.45
};

const nodeStyle = {
radius:4,
color:"#163832",
weight:1,
fillColor:"#e4f4ed",
fillOpacity:0.9
};

campusPaths.forEach((segment) => {
if(!segment || !segment.from || !segment.to) return;
const from = [segment.from.lat, segment.from.lng];
const to = [segment.to.lat, segment.to.lng];

L.polyline([from, to], edgeStyle).addTo(campusGraphLayer);
graphBounds.push(from, to);

const fromKey = `${segment.from.lat},${segment.from.lng}`;
if(!nodeIndex.has(fromKey)){
nodeIndex.add(fromKey);
L.circleMarker(from, nodeStyle)
.addTo(campusGraphLayer)
.bindTooltip(segment.from.name || "Path node");
}

const toKey = `${segment.to.lat},${segment.to.lng}`;
if(!nodeIndex.has(toKey)){
nodeIndex.add(toKey);
L.circleMarker(to, nodeStyle)
.addTo(campusGraphLayer)
.bindTooltip(segment.to.name || "Path node");
}
});

if(!routeLayer && graphBounds.length > 0){
map.fitBounds(graphBounds, {
padding:[40, 40]
});
}
}
