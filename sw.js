const CACHE='moonbus-v35';
const ASSETS=['./','./index.html','./manifest.json','./icon-192.png','./icon-512.png'];
self.addEventListener('install',e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener('fetch',e=>{
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});
// Push提示
self.addEventListener('push',e=>{
  const data=e.data?e.data.json():{title:'MoonBus 異動',body:'主板出現急升股！'};
  e.waitUntil(self.registration.showNotification(data.title,{
    body:data.body, icon:'./icon-512.png', badge:'./icon-192.png'
  }));
});