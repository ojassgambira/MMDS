# AMLSim feasibility assessment

Verdict: **simulation deferred; prerequisites unavailable and compatibility
unverified**. No AMLSim dependency installation or simulation was attempted.

Inspected upstream master README, requirements.txt and pom.xml on 2026-10-14:
- https://github.com/IBM/AMLSim/blob/master/README.md
- https://github.com/IBM/AMLSim/blob/master/requirements.txt
- https://github.com/IBM/AMLSim/blob/master/pom.xml

The README specifies Java 8 and Python 3.7, NetworkX 1.11 and matplotlib 2.2.3;
requirements.txt instead requests matplotlib >=3.1.2, plus unpinned numpy,
pygraphviz, powerlaw, python-dateutil and Faker. NetworkX 1.11 relies on APIs
removed from modern Python (notably fractions.gcd), so Python 3.12 is not a safe
drop-in target. Historical numerical/plotting packages and native pygraphviz
also need a separately tested environment. Do not weaken the main project pins
to accommodate these dependencies.

The inspected Maven file targets Java 1.8 and references MASON 20, JSON 20180813,
WebGraph 3.6.1, Mockito 4.0.0 and JUnit BOM 5.8.1. README also lists Commons Math
3.6.1, dsiutils 2.5.4, fastutil 8.2.3, sux4j 4.2.0, JSAP 2.1 and SLF4J 1.7.25.
MASON requires a separately obtained JAR in the documented Maven workflow.
The runtime has Java 21 JRE, no javac command, no known MASON installation,
no simulator checkout, and no Python 3.7 environment. Java 21 compatibility
cannot be inferred from a Java 8 compiler target.

Next safe experiment: inspect and pin a master commit, prepare a separate cloud
container with the legacy runtime (or audited compatibility patches), resolve
all requirements and hashes, inspect build scripts and obtain trusted MASON
artifacts within policy. Because Python 3.7 is obsolete, isolate this offline
simulation environment from production and secrets. Read cloud Docker guidance
before building. Do not install obsolete dependencies globally.
Use upstream paramFiles/1K, fixed seed 0 and a reduced 10–20 steps, after inspecting
configuration and estimating limits. Run graph generator, Java build/simulator,
then convert_logs only when all prerequisites pass. Cap runtime and output size;
verify deterministic counts, referential integrity and scenario labels. Record
upstream commit, JAR hashes and final runtime lock. None of these steps are
claimed executed, and no simulation metrics are reported.
