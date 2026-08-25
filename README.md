# b4geoip-forkop

## Списки

- **Gaming:** blizzard, bungie, ccp, electronicarts, epicgames, nintendo,
  play2go, riot, roblox, sony, taketwo, ubisoft, valve, wargaming
- **Cloud / CDN:** aeza, akamai, amazon, belcloud, buyvm, cdn77,
  cloudflare, cogent, constant, contabo, datacamp, digitalocean,
  digitalone, fastly, gcore, glesys, gthost, hetzner, meganz, melbicom,
  oracle, ovh, scalaxy, scaleway, vercel, zerocdn
- **Tech:** adobe, anthropic, apple, github, google, meta
- **Messaging:** telegram

## Подключение в sing-box

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "geoip-telegram",
        "format": "binary",
        "url": "https://github.com/Greeg0ry/b4geoip-forkop/releases/latest/download/telegram.srs",
        "download_detour": "direct",
        "update_interval": "1d"
      }
    ]
  }
}
```

Замените `telegram` на нужный список из раздела выше.

## Постоянная ссылка на скачивание

```text
https://github.com/Greeg0ry/b4geoip-forkop/releases/latest/download/<name>.srs
```
