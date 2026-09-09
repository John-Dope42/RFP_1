# SOURCE_RESEARCH – aktueller Quellenkatalog

**Stand: 2026-09-09**

Diese Datei beschreibt den aktuell im Projekt konfigurierten Supplemental-Quellenkatalog (`config/source_catalog.yaml`). Sie ersetzt keine Lizenzprüfung: `authority` beschreibt die fachliche Stellung der Quelle, nicht automatisch eine Trainingslizenz. `use_for` bestimmt, ob die Quelle für QLoRA, RAG oder beides vorgesehen ist.

## Verarbeitungsprinzipien

- HTML/PDF werden mit begrenzter Crawl-Tiefe verarbeitet.
- Öffentliche Git-Repositories werden über Repository-Tree/Raw-Inhalte verarbeitet; GitHub-Navigationsseiten, Issues, Releases und offensichtliche Build-/Asset-Pfade werden nicht als Wissensquellen behandelt.
- Nicht erreichbare Quellen sind grundsätzlich non-fatal; `source_health.py` dokumentiert den Status.
- Provenienz bleibt in den Rohdaten erhalten.
- Recht, Milsim und Militärdoktrin werden in getrennten Domains geführt.

## Quellen nach Domain

### programming

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| microsoft_learn_dotnet | Microsoft Learn .NET | crawl | official | en | both | https://learn.microsoft.com/dotnet/ |
| microsoft_learn_python | Microsoft Learn Python | crawl | official | en | both | https://learn.microsoft.com/training/modules/intro-to-python/ |
| java_oracle_docs | Oracle Java Docs | crawl | official | en | both | https://docs.oracle.com/en/java/ |
| typescript_docs | TypeScript Handbook | crawl | official | en | both | https://www.typescriptlang.org/docs/handbook/intro.html |
| nodejs_docs | Node.js API Docs | crawl | official | en | both | https://nodejs.org/docs/latest/api/ |
| react_docs | React Docs | crawl | official | en | both | https://react.dev/learn |
| cppreference | cppreference | crawl | reference | en | both | https://en.cppreference.com/w/ |
| rust_book | The Rust Book | crawl | official | en | both | https://doc.rust-lang.org/book/ |
| go_docs | Go Documentation | crawl | official | en | both | https://go.dev/doc/ |
| git_docs | Git Documentation | crawl | official | en | both | https://git-scm.com/docs |
| docker_docs | Docker Docs | crawl | official | en | both | https://docs.docker.com/ |
| kubernetes_docs | Kubernetes Docs | crawl | official | en | both | https://kubernetes.io/docs/home/ |
| linux_kernel_docs | Linux Kernel Docs | crawl | official | en | both | https://docs.kernel.org/ |
| postgresql_docs | PostgreSQL Docs | crawl | official | en | both | https://www.postgresql.org/docs/current/ |
| sqlite_docs | SQLite Docs | crawl | official | en | both | https://www.sqlite.org/docs.html |

### science

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| ncbi_bookshelf | NCBI Bookshelf | crawl | official | en | both | https://www.ncbi.nlm.nih.gov/books/ |
| nasa_science | NASA Science | crawl | official | en | both | https://science.nasa.gov/ |
| esa_science | ESA Science | crawl | official | en | both | https://www.esa.int/Science_Exploration |
| noaa_research | NOAA Research | crawl | official | en | both | https://www.noaa.gov/research |
| usgs_science | USGS Science | crawl | official | en | both | https://www.usgs.gov/science |
| nist_research | NIST Research | crawl | official | en | both | https://www.nist.gov/laboratories |
| cern_science | CERN Science | crawl | official | en | both | https://home.cern/science |
| who_science | WHO Science | crawl | official | en | both | https://www.who.int/health-topics |
| openstax_science | OpenStax Science | crawl | open_education | en | both | https://openstax.org/subjects/science |
| national_academies | National Academies | crawl | expert_academy | en | both | https://www.nationalacademies.org/ |
| plos | PLOS | crawl | scientific_publisher | en | rag | https://plos.org/ |
| royal_society | Royal Society | crawl | scientific_academy | en | rag | https://royalsociety.org/ |
| frontiers | Frontiers | crawl | scientific_publisher | en | rag | https://www.frontiersin.org/ |

### philosophy_ethics

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| sep | Stanford Encyclopedia of Philosophy | crawl | academic_reference | en | both | https://plato.stanford.edu/ |
| iep | Internet Encyclopedia of Philosophy | crawl | academic_reference | en | both | https://iep.utm.edu/ |
| philpapers | PhilPapers | crawl | academic_index | en | rag | https://philpapers.org/ |
| philarchive | PhilArchive | crawl | academic_repository | en | rag | https://philarchive.org/ |
| mit_ocw_philosophy | MIT OpenCourseWare Philosophy | crawl | university | en | both | https://ocw.mit.edu/search/?q=philosophy |
| openstax_philosophy | OpenStax Philosophy | crawl | open_education | en | both | https://openstax.org/subjects/humanities |
| internet_classics_archive | Internet Classics Archive | crawl | academic_archive | en | both | http://classics.mit.edu/ |
| gutenberg | Project Gutenberg | crawl | public_domain_archive | en | both | https://www.gutenberg.org/ |
| wikisource_en | English Wikisource | crawl | community_archive | en | rag | https://en.wikisource.org/wiki/Main_Page |
| openlearn | OpenLearn | crawl | university | en | both | https://www.open.edu/openlearn/ |
| ethics_unwrapped | Ethics Unwrapped | crawl | university | en | both | https://ethicsunwrapped.utexas.edu/ |
| plato_de | Deutsche Philosophie Quellen | crawl | archive | de | rag | https://www.textlog.de/ |

### gaertnern

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| rhs | Royal Horticultural Society | crawl | professional_horticulture | en | both | https://www.rhs.org.uk/ |
| kew | Royal Botanic Gardens Kew | crawl | botanical_institution | en | both | https://www.kew.org/ |
| usda_plants | USDA Plants Database | crawl | official | en | both | https://plants.usda.gov/ |
| ncstate_extension | NC State Extension Gardener | crawl | university_extension | en | both | https://extensiongardener.ces.ncsu.edu/ |
| umn_extension | University of Minnesota Extension Garden | crawl | university_extension | en | both | https://extension.umn.edu/yard-and-garden |
| missouri_botanical | Missouri Botanical Garden | crawl | botanical_institution | en | both | https://www.missouribotanicalgarden.org/ |
| rbge | Royal Botanic Garden Edinburgh | crawl | botanical_institution | en | both | https://www.rbge.org.uk/ |
| fao_agriculture | FAO Agriculture | crawl | international_organization | en | both | https://www.fao.org/food-agriculture-statistics/en/ |
| cabi | CABI | crawl | scientific_organization | en | both | https://www.cabi.org/ |
| eppo | EPPO | crawl | international_organization | en | both | https://www.eppo.int/ |
| rhs_plants | RHS Plant Search | crawl | professional_horticulture | en | rag | https://www.rhs.org.uk/plants/search-form |
| jki | Julius Kühn-Institut | crawl | official_research | de | both | https://www.julius-kuehn.de/ |
| bmel_agriculture | BMEL Landwirtschaft | crawl | official | de | both | https://www.bmel.de/ |

### cannabis_zucht_sommelier

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| health_canada_cannabis | Health Canada Cannabis | crawl | official | en | both | https://www.canada.ca/en/health-canada/services/drugs-medication/cannabis.html |
| health_canada_research | Health Canada Cannabis Research | crawl | official | en | both | https://www.canada.ca/en/health-canada/services/drugs-medication/cannabis/industry-licensees-applicants/types-research.html |
| nida_cannabis | NIDA Cannabis Research | crawl | official_research | en | both | https://nida.nih.gov/research-topics/cannabis-marijuana |
| cdc_cannabis | CDC Cannabis | crawl | official_public_health | en | both | https://www.cdc.gov/cannabis/ |
| fda_cannabis | FDA Cannabis | crawl | official | en | both | https://www.fda.gov/news-events/public-health-focus/fda-regulation-cannabis-and-cannabis-derived-products-including-cannabidiol-cbd |
| national_academies_cannabis | National Academies Cannabis Report | crawl | expert_academy | en | both | https://nap.nationalacademies.org/catalog/24625/the-health-effects-of-cannabis-and-cannabinoids |
| journal_cannabis_research | Journal of Cannabis Research | crawl | scientific_journal | en | rag | https://jcannabisresearch.biomedcentral.com/ |
| frontiers_cannabis | Frontiers Cannabis Research | crawl | scientific_publisher | en | rag | https://www.frontiersin.org/research-topics/16712/behind-the-smoke-and-mirrors-reflections-on-improving-cannabis-production-and-investigating-medical-potential |
| emcdda_cannabis_archive | EUDA Cannabis Topic | crawl | official_eu_agency | en | both | https://www.euda.europa.eu/topics/cannabis_en |
| bfr_cannabis | BfR Cannabis Risk Assessment | crawl | official_research | de | both | https://www.bfr.bund.de/ |
| drugscience_cannabis | Drug Science Cannabis | crawl | research_organization | en | rag | https://www.drugscience.org.uk/ |
| pubchem_cannabinoids | PubChem | crawl | official_database | en | rag | https://pubchem.ncbi.nlm.nih.gov/ |

### recht_de_eu

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| bundestag_dip | Deutscher Bundestag Dokumentation | crawl | official | de | both | https://www.bundestag.de/dokumente |
| bundesrat | Bundesrat | crawl | official | de | both | https://www.bundesrat.de/ |
| bverfg | Bundesverfassungsgericht | crawl | official_court | de | both | https://www.bundesverfassungsgericht.de/ |
| bgh | Bundesgerichtshof | crawl | official_court | de | both | https://www.bundesgerichtshof.de/ |
| bverwg | Bundesverwaltungsgericht | crawl | official_court | de | both | https://www.bverwg.de/ |
| bag | Bundesarbeitsgericht | crawl | official_court | de | both | https://www.bundesarbeitsgericht.de/ |
| bsg | Bundessozialgericht | crawl | official_court | de | both | https://www.bsg.bund.de/ |
| bfh | Bundesfinanzhof | crawl | official_court | de | both | https://www.bundesfinanzhof.de/ |
| curia | CURIA EuGH | crawl | official_court | de | both | https://curia.europa.eu/ |
| eu_justice | European e-Justice | crawl | official_eu | en | both | https://e-justice.europa.eu/ |
| recht_bund | Bundesgesetzblatt Portal | crawl | official | de | both | https://www.recht.bund.de/ |
| nlex | N-Lex | crawl | official_eu | en | rag | https://n-lex.europa.eu/ |
| bpatg | Bundespatentgericht | crawl | official_court | de | both | https://www.bundespatentgericht.de/ |

### arma3_technical

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| arma3_samples | Bohemia Arma 3 Samples | github | official_developer | en | both | https://community.bohemia.net/wiki/Arma_3%3A_Asset_Samples |
| arma3_tools | Arma 3 Tools Wiki Category | crawl | official_community_documentation | en | both | https://community.bohemia.net/wiki/Category:Arma_3%3A_Official_Tools |
| arma3_modding | Arma 3 Modding Category | crawl | official_community_documentation | en | both | https://community.bohemia.net/wiki/Category:Arma_3%3A_Editing |
| cba_repo | CBA_A3 Repository | github | project_documentation | en | both | https://github.com/CBATeam/CBA_A3 |
| ace3_repo | ACE3 Repository | github | project_documentation | en | both | https://github.com/acemod/ACE3 |
| alive_repo | ALiVE.OS | github | project_documentation | en | both | https://github.com/ALiVEOS/ALiVE.OS |
| antistasi_repo | A3 Antistasi | github | project_documentation | en | both | https://github.com/A3Antistasi/A3-Antistasi |
| acre2_repo | ACRE2 | github | project_documentation | en | both | https://github.com/IDI-Systems/acre2 |
| tfar_repo | Task Force Arma 3 Radio | github | project_documentation | en | both | https://github.com/michail-nikolaev/task-force-arma-3-radio |
| cup_project_site | CUP (Community Upgrade Project) | crawl | project_documentation | en | rag | https://www.cup-arma3.org/ |
| arma3_units | Arma 3 Units | crawl | community | en | rag | https://units.arma3.com/ |

### military_general

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| nato_strategic_concepts | NATO Strategic Concepts | crawl | official_primary | en | both | https://www.nato.int/en/about-us/official-texts-and-resources/strategic-concepts |
| nato_topics | NATO Topics | crawl | official_primary | en | both | https://www.nato.int/en/about-us/official-texts-and-resources |
| jcs_joint_doctrine | Joint Chiefs Joint Doctrine | crawl | official_primary | en | both | https://www.jcs.mil/Doctrine/Joint-Doctrine-Pubs/ |
| jcs_operations | Joint Operations Doctrine | crawl | official_primary | en | both | https://www.jcs.mil/doctrine/joint-doctrine-pubs/3-0-operations-series/ |
| army_university_press | Army University Press | crawl | official_primary | en | both | https://www.armyupress.army.mil/Journals/ |
| military_review | Military Review | crawl | official_primary | en | rag | https://www.armyupress.army.mil/Journals/Journals/Military-Review/ |
| tradoc | T2COM (Nachfolgeorganisation von TRADOC) | crawl | official_primary | en | both | https://www.army.mil/t2com |
| defence_academy_uk | UK Defence Academy | crawl | official_primary | en | rag | https://www.da.mod.uk/ |
| zmsbw | ZMSBw | crawl | official_research | de | both | https://zms.bundeswehr.de/ |
| ifsh | IFSH | crawl | research_institute | de | rag | https://ifsh.de/ |
| swp | Stiftung Wissenschaft und Politik | crawl | research_institute | de | rag | https://www.swp-berlin.org/ |
| dcdc | UK Defence Futures (vormals DCDC) | crawl | official_primary | en | both | https://www.gov.uk/government/groups/development-concepts-and-doctrine-centre |

### milsim

| ID | Quelle | Modus | Autorität | Sprache | Nutzung | URL |
|---|---|---|---|---|---|---|
| shack_tactical | Shack Tactical | crawl | community_milsim | en | both | https://dslyecxi.com/ |
| bohemia_forums | Bohemia Interactive Forums | crawl | community | en | rag | https://forums.bohemia.net/ |
| arma_units | Arma 3 Units | crawl | community | en | rag | https://units.arma3.com/ |
| antistasi_milsim | Antistasi Repository | github | community_project | en | both | https://github.com/A3Antistasi/A3-Antistasi |
| alive_milsim | ALiVE Repository | github | community_project | en | both | https://github.com/ALiVEOS/ALiVE.OS |
| acre2_milsim | ACRE2 Repository | github | community_project | en | both | https://github.com/IDI-Systems/acre2 |
| tfar_milsim | TFAR Repository | github | community_project | en | both | https://github.com/michail-nikolaev/task-force-arma-3-radio |
| ace3_milsim | ACE3 Repository | github | community_project | en | both | https://github.com/acemod/ACE3 |
| arma_general_guides | Arma 3 General Guides Compilation | crawl | community | en | both | https://forums.bohemia.net/forums/topic/227697-arma-3-general-game-guides-faqs-manuals-tutorials-compilation/ |
| arma_steam_workshop | Arma 3 Steam Workshop | crawl | community | en | rag | https://steamcommunity.com/workshop/browse/?appid=107410 |
| arma3_modding_community | Arma 3 Modding Community | crawl | community | en | rag | https://forums.bohemia.net/forums/forum/116-arma-3-editing/ |
| arma_scripting_forum | Arma 3 Scripting Forum | crawl | community | en | rag | https://forums.bohemia.net/forums/forum/162-arma-3-scripting/ |

## Lizenz-/Redistribution-Regel

Ein Eintrag im Katalog ist **keine** Zusicherung, dass der gesamte Inhalt frei für Modelldistribution ist. Besonders bei wissenschaftlichen Verlagen, Community-Seiten und aggregierten Portalen muss die konkrete Lizenz des tatsächlich extrahierten Inhalts geprüft werden. Bei Unsicherheit nur Metadaten/RAG-Referenzen verwenden oder eine explizit wiederverwendbare Quelle einsetzen.

## Source Health

Vor einem großen Crawl:

```bash
python scripts/source_health.py
```

Die Ergebnisse werden unter `data/reports/source_health.json` gespeichert. Ein `403`/`429` bedeutet „erreichbar, aber automatisierter Zugriff eingeschränkt“ und ist nicht mit „Quelle existiert nicht“ gleichzusetzen.

## Core-Quellen

`config/sources.yaml` enthält die älteren/core-spezifischen Quellen für Cannabis, Recht, Arma 3, Militär und Lifehacks. Diese Datei und der Supplemental-Katalog werden bewusst getrennt gehalten: Core-Collector besitzen teilweise eigene Parser/API-Logik, während Supplemental-Quellen generisch verarbeitet werden.

## Aktualität

Quellen sind live und können ihre URL, HTML-Struktur, Lizenz oder Zugriffsregeln ändern. Deshalb sollte `source_health.py` vor umfangreichen Sammelläufen erneut ausgeführt werden. Eine einmal erfolgreich geprüfte Quelle bleibt keine dauerhafte Verfügbarkeitsgarantie.
