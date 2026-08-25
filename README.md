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

Каждый файл — готовый rule-set с CIDR одной категории (`geoip:<name>` из
b4geoip). Есть два источника, оба обновляются одним и тем же workflow:

**1. Файлы в репозитории** ([`srs/`](./srs), всегда актуальная версия на
`main`):

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

**2. Ассеты в [Releases](../../releases)** — как у
[itdoginfo/allow-domains](https://github.com/itdoginfo/allow-domains).
Каждый успешный запуск публикует новый релиз с тем же набором `.srs` в
качестве ассетов; `.../releases/latest/download/<name>.srs` всегда указывает
на файлы из последнего релиза:

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

Замените `telegram` на нужную категорию.

## Категории

`geoip.dat` от b4geoip расширяет базу
[RUNETFREEDOM](https://github.com/runetfreedom/russia-blocked-geoip) полным
набором кодов стран ISO 3166-1 и служебными списками (`tor`, `private`,
`ru-blocked` и т.п.) — но сюда, в `srs/`, попадают **только** оригинальные
сервисные категории самого b4geoip (список зафиксирован в `wantedList`
внутри [`srs-config.json`](./srs-config.json)):

- **Gaming:** blizzard, bungie, ccp, electronicarts, epicgames, nintendo,
  play2go, riot, roblox, sony, taketwo, ubisoft, valve, wargaming
- **Cloud / CDN:** aeza, akamai, amazon, belcloud, buyvm, cdn77,
  cloudflare, cogent, constant, contabo, datacamp, digitalocean,
  digitalone, fastly, gcore, glesys, gthost, hetzner, meganz, melbicom,
  oracle, ovh, scalaxy, scaleway, vercel, zerocdn
- **Tech:** adobe, anthropic, apple, github, google, meta
- **Messaging:** telegram

Итого 47 файлов `.srs`. Страновые списки (`ru.srs`, `us.srs`, …) и прочие
данные, унаследованные от RUNETFREEDOM, намеренно не публикуются. Если
b4geoip добавит новую категорию в этот же набор, её нужно будет вручную
дописать в `wantedList` — автоматически новые категории не подхватываются.

## Ручной запуск

Workflow можно запустить вручную во вкладке Actions → *Build sing-box
rule-sets from b4geoip* → *Run workflow*.

> Чтобы workflow мог пушить обновлённые `.srs` в `main`, в настройках
> репозитория (Settings → Actions → General → Workflow permissions) должно
> быть выбрано **Read and write permissions**.
