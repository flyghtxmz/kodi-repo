import assert from "node:assert/strict";
import test from "node:test";
import {torrentioBaseUrl,explicitLanguage,fromTorrentioPayload,mergeSources,queryTorrentio} from "../src/torrentio.mjs";

const A="a".repeat(40),B="b".repeat(40),C="c".repeat(40);
test("Torrentio endpoint is host allowlisted without embedding credentials",()=>{
  assert.equal(torrentioBaseUrl().startsWith("https://torrentio.strem.fun/"),true);
  assert.throws(()=>torrentioBaseUrl("https://evil.example/"),/invalid/);
  assert.throws(()=>torrentioBaseUrl("http://torrentio.strem.fun/"),/invalid/);
  assert.throws(()=>torrentioBaseUrl("https://torrentio.strem.fun/realdebrid=secret"),/credentials/);
});
test("language is marked only for explicit metadata, not provider name",()=>{
  assert.equal(explicitLanguage("Carrie 1080p DUBLADO"),"pt-br");
  assert.equal(explicitLanguage("Carrie 1080p Dual Audio"),"pt-br");
  assert.equal(explicitLanguage("Carrie 1080p Português"),"pt-br");
  assert.equal(explicitLanguage("Carrie 1080p [MicoLeaoDublado]".replace("Dublado]","Dublado]")),"pt-br");
  assert.equal(explicitLanguage("Carrie BluDV 1080p"),"unknown");
  assert.equal(explicitLanguage("Carrie 1080p English"),"other");
});
test("hash duplicates are removed, explicit PTBR wins",()=>{
  const output=fromTorrentioPayload({streams:[
    {infoHash:A,name:"Torrentio 1080p",title:"Carrie 1080p 💾 2 GB 👤 12"},
    {infoHash:A,name:"Torrentio",title:"Carrie 1080p DUBLADO 💾 2 GB 👤 5",fileIdx:2},
    {infoHash:B,name:"Torrentio 4K",title:"Carrie 2160p 💾 7.1 GB 👤 50"},
    {infoHash:C,title:"Carrie 720p Português",fileIdx:0},
    {url:"https://untrusted.example/video.mp4",title:"not torrent"},
  ]});
  assert.equal(output.stats.raw,5);
  assert.equal(output.stats.hash_valid,4);
  assert.equal(output.stats.unique,3);
  assert.equal(output.stats.repeated_hashes,1);
  assert.equal(output.sources[0].language,"pt-br");
  assert.equal(output.sources[0].infoHash,A);
  assert.equal(output.sources[0].fileIdx,2);
  assert.equal(output.sources[0].audio_verified,false);
  assert.equal(output.sources[0].source,"Torrentio");
  assert.equal(output.sources[1].language,"pt-br");
});
test("merge deduplicates existing provider torrents by infohash",()=>{
  const existing=[{source:"Parceiro",url:"magnet:?xt=urn:btih:"+A,
                   title:"Carrie",quality:"SD",language:"unknown"}];
  const newOne=[{source:"Torrentio",url:"magnet:?xt=urn:btih:"+A,
                 infoHash:A,title:"Carrie PT-BR",quality:"1080p",language:"pt-br"}];
  const out=mergeSources(existing,newOne);
  assert.equal(out.length,1);
  assert.equal(out[0].source,"Torrentio");
});
test("failed Torrentio upstream does not get guessed as available",async()=>{
  await assert.rejects(queryTorrentio("tt1234567",{fetcher:async()=>({
    ok:false,status:504,headers:{get:()=>null},text:async()=>""})}),/504/);
});
test("query uses IMDb and parses 23 raw items in mock",async()=>{
  let called="";
  const item={infoHash:A,name:"Torrentio 1080p",title:"Carrie Português 👤 8 💾 1.2 GB"};
  const out=await queryTorrentio("tt1234567",{
    fetcher:async(url)=>{
      called=url;
      return {ok:true,headers:{get:()=>null},text:async()=>JSON.stringify({streams:Array(23).fill(item)})};
    }
  });
  assert.match(called,/\/stream\/movie\/tt1234567\.json$/);
  assert.equal(out.stats.raw,23);
  assert.equal(out.stats.unique,1);
  assert.equal(out.stats.repeated_hashes,22);
});
test("invalid IMDb never touches network",async()=>{
  const out=await queryTorrentio("bad",{fetcher:()=>{throw Error("must not fetch");}});
  assert.equal(out.sources.length,0);
});
