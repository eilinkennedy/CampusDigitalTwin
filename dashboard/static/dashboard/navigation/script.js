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
