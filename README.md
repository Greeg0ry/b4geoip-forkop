# b4geoip-forkop

Автоматически, раз в сутки (00:00 по Москве), скачивает свежий
[`geoip.dat`](https://github.com/DanielLavrushin/b4geoip) от
[DanielLavrushin/b4geoip](https://github.com/DanielLavrushin/b4geoip) и
конвертирует каждую его категорию в отдельный бинарный rule-set
[sing-box](https://sing-box.sagernet.org/) (`.srs`) — по аналогии с тем, как
это делает [itdoginfo/allow-domains](https://github.com/itdoginfo/allow-domains)
для доменных списков.

Конвертация выполняется утилитой
[Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) (формат
`v2rayGeoIPDat` → `singboxSRS`), см. [`srs-config.json`](./srs-config.json) и
[`.github/workflows/build-srs.yml`](./.github/workflows/build-srs.yml).

## Как подключить в sing-box

Каждый файл в каталоге [`srs/`](./srs) — готовый rule-set с CIDR одной
категории (`geoip:<name>` из b4geoip). Подключается как `remote` rule-set:

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "geoip-telegram",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/Greeg0ry/b4geoip-forkop/main/srs/telegram.srs",
        "download_detour": "direct",
        "update_interval": "1d"
      }
    ]
  }
}
```

Замените `telegram` на нужную категорию.

## Категории

`geoip.dat` от b4geoip расширяет базу
[RUNETFREEDOM](https://github.com/runetfreedom/russia-blocked-geoip), поэтому
в `srs/` оказывается ~300 файлов:

- коды стран ISO 3166-1 alpha-2 из базы RUNETFREEDOM (`ru.srs`, `us.srs`,
  `de.srs`, …), плюс служебные списки вроде `tor.srs`;
- сервисные категории самого b4geoip:
  - **Gaming:** blizzard, bungie, ccp, electronicarts, epicgames, nintendo,
    play2go, riot, roblox, sony, taketwo, ubisoft, valve, wargaming
  - **Cloud / CDN:** aeza, akamai, amazon, belcloud, buyvm, cdn77,
    cloudflare, cogent, constant, contabo, datacamp, digitalocean,
    digitalone, fastly, gcore, glesys, gthost, hetzner, meganz, melbicom,
    oracle, ovh, scalaxy, scaleway, vercel, zerocdn
  - **Tech:** adobe, anthropic, apple, github, google, meta
  - **Messaging:** telegram

Список файлов в точности повторяет содержимое очередного `geoip.dat` — если
в исходной базе появится новая категория или страна, при следующем запуске
здесь появится соответствующий `.srs`-файл автоматически.

## Ручной запуск

Workflow можно запустить вручную во вкладке Actions → *Build sing-box
rule-sets from b4geoip* → *Run workflow*.

> Чтобы workflow мог пушить обновлённые `.srs` в `main`, в настройках
> репозитория (Settings → Actions → General → Workflow permissions) должно
> быть выбрано **Read and write permissions**.
