"""Sample sources: every one validates and renders (the tests check it)."""

from __future__ import annotations

import json

#: An order lifecycle: a compound checkout with a history state, a parallel fulfilment
#: whose two regions both have to finish, guarded alternatives and final states.
ORDER = json.dumps(
    {
        "id": "order",
        "title": "Order lifecycle",
        "initial": "cart",
        "context": {"items": 0, "total": 0},
        "states": {
            "cart": {
                "description": "The shopper is still adding items.",
                "on": {
                    "ADD_ITEM": {"actions": ["addItem"]},
                    "CHECKOUT": {"target": "checkout", "guard": "hasItems"},
                },
            },
            "checkout": {
                "initial": "address",
                "entry": ["startTimer"],
                "exit": ["stopTimer"],
                "description": "Address, then payment. Help keeps your place.",
                "states": {
                    "address": {"on": {"NEXT": "payment"}},
                    "payment": {
                        "on": {
                            "BACK": "address",
                            "PAY": [
                                {
                                    "target": "#order.fulfilment",
                                    "guard": "cardOk",
                                    "actions": ["charge"],
                                },
                                {"target": "declined", "guard": "cardDeclined"},
                            ],
                        }
                    },
                    "declined": {"on": {"RETRY": "payment"}},
                    "hist": {"type": "history"},
                },
                "on": {"HELP": "help", "CANCEL": "cancelled"},
            },
            "help": {
                "description": "A support chat; resuming returns to the same checkout step.",
                "on": {"RESUME": "checkout.hist"},
            },
            "fulfilment": {
                "type": "parallel",
                "description": "Packing and invoicing run at the same time.",
                "onDone": "delivered",
                "states": {
                    "packing": {
                        "initial": "picking",
                        "states": {
                            "picking": {"on": {"PACKED": "packed"}},
                            "packed": {"type": "final"},
                        },
                    },
                    "invoice": {
                        "initial": "drafting",
                        "states": {
                            "drafting": {"on": {"SEND": "sent"}},
                            "sent": {"type": "final"},
                        },
                    },
                },
                "on": {"CANCEL": {"target": "cancelled", "actions": ["refund"]}},
            },
            "delivered": {"type": "final", "entry": ["notifyCustomer"]},
            "cancelled": {"type": "final"},
        },
    },
    indent=2,
    ensure_ascii=False,
)

#: A traffic light: a compound red phase and a parallel maintenance mode.
TRAFFIC_LIGHT = json.dumps(
    {
        "id": "light",
        "title": "Traffic light",
        "initial": "green",
        "direction": "TB",
        "states": {
            "green": {"on": {"TIMER": "yellow"}},
            "yellow": {"on": {"TIMER": "red"}},
            "red": {
                "initial": "walk",
                "states": {
                    "walk": {"on": {"COUNTDOWN": "wait"}},
                    "wait": {"on": {"COUNTDOWN": "stop"}},
                    "stop": {"type": "final"},
                },
                "onDone": "green",
            },
            "maintenance": {
                "type": "parallel",
                "states": {
                    "lamp": {
                        "initial": "on",
                        "states": {
                            "on": {"on": {"BLINK": "off"}},
                            "off": {"on": {"BLINK": "on"}},
                        },
                    },
                    "crew": {
                        "initial": "working",
                        "states": {
                            "working": {"on": {"FINISH": "done"}},
                            "done": {"type": "final"},
                        },
                    },
                },
                "on": {"RESUME": "red"},
            },
        },
        "on": {"FAULT": {"target": ".maintenance", "actions": ["alertCrew"]}},
    },
    indent=2,
    ensure_ascii=False,
)

EXAMPLE = ORDER

TEMPLATE = json.dumps(
    {
        "id": "machine",
        "title": "My state machine",
        "initial": "idle",
        "states": {
            "idle": {"on": {"START": "running"}},
            "running": {
                "entry": ["begin"],
                "on": {"PAUSE": "paused", "FINISH": "done"},
            },
            "paused": {"on": {"RESUME": "running"}},
            "done": {"type": "final"},
        },
    },
    indent=2,
)

SAMPLES = {"order": ORDER, "traffic_light": TRAFFIC_LIGHT, "template": TEMPLATE}
