# Opgeslagen Assists bekijken

Deze voorbereiding toont de drie favorietenplaatsen die de X PURE-app
gebruikt: **Saved Assist 3**, **Saved Assist 4** en **Saved Assist 5**.
De apparaatmetadata moet X PURE en een passende indexrange melden.
Dit is uitsluitend uitlezen; de opgeslagen inhoud wordt niet gewijzigd.

Druk op **Refresh saved Assists** om één `GetSavedCsf`-vraag te doen.
De knop werkt ook met algemene bediening en kookbediening uitgeschakeld.
Opstarten, gewone statuscontroles en verbindingsherstel lezen deze lijst
niet automatisch. De bestaande knop **Refresh diagnostics** doet deze
vraag al en vult hetzelfde overzicht, zonder een tweede favorietenvraag.

## Betekenis van de weergave

| Weergave | Betekenis |
| --- | --- |
| Onbeschikbaar | Nog niet uitgelezen, uitlezing mislukt of verbinding ongeldig. Er wordt geen lege plaats aangenomen. |
| Programmatitel | Het ontvangen programma-ID én type komen overeen met een van de vier bekende FRYING-catalogusprogramma's. |
| `unknown_<id>` | De plaats is gevuld, maar het ID/type-paar is niet als catalogusprogramma herkend. |
| `empty` | Een geslaagde uitlezing bevat geen parameter voor deze plaats. |
| `ambiguous` | De response bevat meerdere parameters voor dezelfde plaats. Geen daarvan wordt stilzwijgend gekozen. |

Het attribuut `last_read` geeft het tijdstip van deze lokale uitlezing in
UTC, niet een tijdstempel van de kookplaat. De ontvangen parameters blijven
zichtbaar als attributen, zonder onbewezen timer- of temperatuurconversies.
De weergave is een momentopname; wijzigingen via de app vragen een nieuwe
uitlezing. De volgorde van de responselijst bepaalt geen plaatsnummer:
de code gebruikt het expliciete `csf_index`.

Bij een nieuwe uitlezing verdwijnen eerst de oude waarden. Na een fout of
annulering blijven ze onbekend. Verbindingsverlies, opnieuw initialiseren en
afsluiten wissen de weergave eveneens. Een laat antwoord uit een oude
verbinding mag haar niet opnieuw vullen. Een diagnostiekdownload leest
alleen de al aanwezige gegevens en veroorzaakt geen apparaatverkeer.

## Nog geen opgeslagen programma starten of bewaren

Een herkende titel bewijst geen veilige startparameters. De bekende
afwijking tussen opslag- en starttimers en het firmwaregedrag bij
weggelaten opslagplaatsen blijven open. Deze uitleesfunctie vult geen
lokale startkeuze in en verstuurt geen `SaveCsf`, `StartOrModifyCsf`,
fasebevestiging of wijziging van een kookzone.

Het app-savepad en de open bewaarvraag staan in
[TIMER-EVIDENCE.md](TIMER-EVIDENCE.md). Alle tests van dit overzicht zijn
offline uitgevoerd; de eerste echte GetSavedCsf-proef moet nog plaatsvinden.
