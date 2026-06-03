# semiautomatic_termino

Daily-cron automation around [termino.gv.at](https://www.termino.gv.at/): it
reads supervisor (VL) assignments from your group's cloud, syncs the schedule
with Termino, sends confirmation and reminder mails, alerts every supervisor
about tomorrow's slot, and optionally drops each slot into a shared calendar.

This documentation is generated with Sphinx + MyST and hosted on Read the Docs.

```{toctree}
:maxdepth: 2
:caption: Getting started

getting-started/installation
getting-started/configuration
getting-started/secrets
```

```{toctree}
:maxdepth: 2
:caption: Using it

usage/daily-run
```

```{toctree}
:maxdepth: 2
:caption: Deployment

deployment/server-cron
deployment/vpn-setup
```

```{toctree}
:maxdepth: 2
:caption: Reference

architecture/overview
reference/api/index
troubleshooting
```
