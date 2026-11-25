# Kontener „jak świeży serwer staging” do make ansible-test (bramka G3): Ubuntu 24.04 z systemd
# jako PID 1, użytkownik ubuntu z sudo bez hasła (jak obraz OCI), bez katalogu
# journald.conf.d (świeży obraz OCI go nie ma; przebieg ansible-staging 45472289719).
FROM ubuntu:24.04@sha256:562111b88caa79c71391c0c4d3c2114a7d5c35915c20561fd893cb1e07929e6b
ENV DEBIAN_FRONTEND=noninteractive
# Wyjątek DL3008 (wersje apt): to obraz testowy „jak świeży serwer”, a nie obraz produkcyjny.
# Obraz bazowy jest przypięty do digestu; konkretne wersje pakietów apt znikają z archiwum
# Ubuntu po aktualizacjach, więc ich przypięcie psułoby test bez zysku. Bez wyjątku hadolint
# zgłasza DL3008 (sprawdzone 25.11.2026).
# hadolint ignore=DL3008
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends systemd systemd-sysv python3 sudo \
       openssh-server iproute2 kmod udev e2fsprogs ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && (id ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu) \
    && echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/90-ubuntu \
    && rm -rf /etc/systemd/journald.conf.d
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
