"""Test fixtures and configuration for the test suite."""

import pytest


@pytest.fixture
def sample_legal_text():
    """Sample text resembling a Moose General Laws section."""
    return """
Chapter 2 — Administration

Article V — Officers and Their Duties

Section 24.3 — Authority Over Bar Operations

(a) Governor's Authority. The Governor shall have full authority over all
officers and employees of the Lodge including hiring and termination. The
Governor may delegate day-to-day supervisory responsibilities to the
Administrator but retains ultimate authority over all personnel decisions.

(b) Administrator's Role. The Administrator shall oversee day-to-day bar
operations and staff scheduling. The Administrator shall report directly to
the Governor on all matters concerning bar operations and personnel.

(c) Limitations. Nothing in this section shall be construed to authorize
any action contrary to federal, state, or local employment laws.
"""


@pytest.fixture
def sample_handbook_text():
    """Sample text resembling an Officer Handbook."""
    return """
PART I: LODGE OFFICERS

Governor — Duties and Responsibilities

The Governor is the chief executive officer of the Lodge. The Governor shall
preside at all meetings of the Lodge and the Board of Officers.

Authority Over Personnel
The Governor has full authority over all employees of the Lodge. This includes
hiring, termination, and discipline of any employee.

Junior Governor

The Junior Governor shall assist the Governor and shall preside in the
Governor's absence. The Junior Governor shall oversee all committees.

Treasurer

The Treasurer shall have custody of all Lodge funds. The Treasurer shall
maintain accurate financial records and present monthly reports.
"""


@pytest.fixture
def sample_ritual_text():
    """Sample text resembling ritual/ceremonial content."""
    return """
OPENING CEREMONY

[Governor]: I now declare this meeting of Moose Lodge #1234 open for the
transaction of such business as may properly come before it.

[All]: I pledge allegiance to the flag of the United States of America.

[Prelate]: Let us bow our heads in prayer. Almighty God, we ask Thy blessing
upon this assembly. Guide our deliberations and help us to act in accordance
with the principles of our Order. Amen.

9 O'CLOCK CEREMONY

[Governor]: It is now nine o'clock. Let every Moose face Mooseheart with
bowed head and folded arms and repeat the silent prayer: "Let the little
children come unto me, do not keep them away."
"""


@pytest.fixture
def sample_newsletter_text():
    """Sample text resembling a Moose Leader article."""
    return """
Moose Leader — October-December 2023

GOVERNOR'S MESSAGE
By Scott D. Hart, Chief Executive Officer

As we close out another year, I want to thank every member of the Moose
Fraternity for your dedication to our mission. This year saw record
membership growth and unprecedented charitable contributions.

MEMBERSHIP DRIVE RESULTS
By Sarah Johnson, Membership Director

The Fall Membership Drive exceeded all expectations with 12,437 new members
joining across all jurisdictions. Lodge #1234 in Springfield, IL led the
nation with 87 new members.
"""
