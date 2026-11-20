# b4geoip-forkop

## Списки

- **Gaming:** blizzard, bungie, ccp, electronicarts, epicgames, nintendo,
  play2go, riot, roblox, sony, taketwo, ubisoft, valve, wargaming, xbox
- **Tech:** adobe, anthropic, apple, google, slack
- **Streaming:** twitch

Xbox, Slack и Twitch скачиваются напрямую из
[v2fly/domain-list-community](https://github.com/v2fly/domain-list-community/tree/master/data).
Вложенные списки Xbox (Bethesda, Forza, Mojang) также загружаются; точные домены
`full:` сохраняются как точные совпадения.

Сборка обновляет `srs/*.srs` ежедневно. Если источник не скачался после трёх
попыток, соответствующий `.srs` сохраняется из предыдущей сборки, а остальные
списки продолжают обновляться. Если недоступен `geoip.dat` или его контрольная
сумма, сохраняются все наборы из этого источника. Для объединённых игровых
наборов сохраняется весь предыдущий файл, включая домены и IP-сети.
В GitHub Actions выводятся предупреждения и перечень сохранённых наборов.
Если предыдущего файла нет, сборка завершается ошибкой. Ошибки формата,
контрольной суммы и компиляции также останавливают публикацию.

Локальная сборка: `python3 -m scripts.build_rulesets` (нужны `geoip` и `sing-box`).

## Игровые наборы

| Игра | Файл |
| --- | --- |
| Apex Legends / Rocket League | `apexlegends_rocketleague.srs` |
| Arknights | `arknights.srs` |
| Arma Reforger | `armareforger.srs` |
| Battlefield 6 | `battlefield6.srs` |
| Blue Archive | `bluearchive.srs` |
| Call of Duty | `callofduty.srs` |
| Company of Heroes 2 | `companyofheroes2.srs` |
| Warhammer 40,000: Darktide | `darktide.srs` |
| Dead by Daylight | `deadbydaylight.srs` |
| Fallout 76 | `fallout76_aws.srs` |
| Gears of War | `gearsofwar.srs` |
| Goose Goose Duck | `goosegooseduck.srs` |
| Magic: The Gathering Arena | `magicthegathering.srs` |
| Minecraft | `minecraft_extra.srs` |
| Mortal Kombat 1 | `mortalkombat1.srs` |
| Mortal Kombat 11 | `mortalkombat11.srs` |
| The Outlast Trials | `outlasttrials.srs` |
| Photon Engine | `photonengine.srs` |
| Street Fighter 6 | `streetfighter6.srs` |
| VRChat | `vrchat.srs` |
| WARDOGS | `wardogs.srs` |
| Warframe | `warframe.srs` |
| Wuthering Waves | `wutheringwaves.srs` |
