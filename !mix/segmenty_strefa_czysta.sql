-- Segmenty dla strefy czystej - wykorzystujące nazwy węzłów z diagramu
-- Autor: wygenerowane na podstawie diagramu topologia.drawio - strefa_czysta

-- Najpierw dodajemy nowe węzły rurociągu zgodnie z diagramem
INSERT INTO `wezly_rurociagu` (`nazwa_wezla`) VALUES
('w_b1c_in'),
('w_b1c_out'),
('w_b9c_in'),
('w_b9c_out'),
('w_pompa_b12c'),
('w_pompa_mieszanki_down'),
('w_pompa_mieszanki_up'),
('w_pompa_mieszanki_rurociag'),
('w_fz_fn_oczyszczalnia');

-- Dodajemy nowe zawory dla strefy czystej
INSERT INTO `zawory` (`nazwa_zaworu`, `stan`) VALUES
('V_B12c_OUT_W_B1c_OUT', 'ZAMKNIETY'),
('V_W_B1c_IN_B12c_IN', 'ZAMKNIETY'),
('V_W_POMPA_B12c_W_B1c_IN', 'ZAMKNIETY'),
('V_CYSTERNA_B12c_W_POMPA_B12c', 'ZAMKNIETY'),
('V_BIALA_W_POMPA_B12c', 'ZAMKNIETY'),
('V_B9c_OUT_W_B9c_OUT', 'ZAMKNIETY'),
('V_B8c_OUT_W_B9c_OUT', 'ZAMKNIETY'),
('V_W_B9c_IN_B9c_IN', 'ZAMKNIETY'),
('V_W_B9c_IN_B8c_IN', 'ZAMKNIETY'),
('V_W_B9c_OUT_W_POMPA_MIESZANKI_RUROCIAG', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_UP_W_B9c_IN', 'ZAMKNIETY'),
('V_W_POMPA_MIESZANKI_UP_W_FZ_FN_OCZYSZCZALNIA', 'ZAMKNIETY'),
('V_W_FZ_FN_OCZYSZCZALNIA_ZEWNETRZNE', 'ZAMKNIETY');

-- Segmenty główne dla beczki B12c (używając Twoich nazw węzłów w_b1c_*)
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_portu_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_B12c_OUT_W_B1c_OUT', 84, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B12c_OUT_W_B1c_OUT'));

INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_portu_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B1c_IN_B12c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_in'), 69, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B1c_IN_B12c_IN'));

-- Segmenty dla pompy B12c
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_POMPA_B12c_W_B1c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b1c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_B12c_W_B1c_IN'));

-- Segmenty dla cystern podłączonych do pompy B12c
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_portu_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_CYSTERNA_B12c_W_POMPA_B12c', 123, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_CYSTERNA_B12c_W_POMPA_B12c')),
('SEGM_BIALA_W_POMPA_B12c', 122, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_b12c'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_BIALA_W_POMPA_B12c'));

-- Segmenty dla beczek B9c i B8c (używając Twoich nazw węzłów w_b9c_*)
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_portu_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_B9c_OUT_W_B9c_OUT', 81, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B9c_OUT_W_B9c_OUT')),
('SEGM_B8c_OUT_W_B9c_OUT', 80, (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_B8c_OUT_W_B9c_OUT'));

INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_portu_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B9c_IN_B9c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), 66, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_IN_B9c_IN')),
('SEGM_W_B9c_IN_B8c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), 65, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_IN_B8c_IN'));

-- Segmenty dla systemu pomp mieszanki (zgodnie z Twoimi nazwami)
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_B9c_OUT_W_POMPA_MIESZANKI_RUROCIAG', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_out'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_B9c_OUT_W_POMPA_MIESZANKI_RUROCIAG')),
('SEGM_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_rurociag'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN')),
('SEGM_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_down'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP')),
('SEGM_W_POMPA_MIESZANKI_UP_W_B9c_IN', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_b9c_in'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_UP_W_B9c_IN'));

-- Segmenty dla oczyszczalni (zgodnie z Twoim węzłem w_fz_fn_oczyszczalnia)
INSERT INTO `segmenty` (`nazwa_segmentu`, `id_wezla_startowego`, `id_wezla_koncowego`, `id_zaworu`) VALUES
('SEGM_W_POMPA_MIESZANKI_UP_W_FZ_FN_OCZYSZCZALNIA', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_pompa_mieszanki_up'), (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_fz_fn_oczyszczalnia'), (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_POMPA_MIESZANKI_UP_W_FZ_FN_OCZYSZCZALNIA')),
('SEGM_W_FZ_FN_OCZYSZCZALNIA_ZEWNETRZNE', (SELECT id FROM wezly_rurociagu WHERE nazwa_wezla = 'w_fz_fn_oczyszczalnia'), NULL, (SELECT id FROM zawory WHERE nazwa_zaworu = 'V_W_FZ_FN_OCZYSZCZALNIA_ZEWNETRZNE'));

-- Dodatkowe porty sprzętu dla nowych elementów
INSERT INTO `porty_sprzetu` (`id_sprzetu`, `nazwa_portu`, `typ_portu`) VALUES
(115, 'BIALA_OUT', 'OUT'),        -- ID 122 - cysterna biała
(116, 'CYSTERNA_B12c_OUT', 'OUT'); -- ID 123 - cysterna B12c

-- Dodanie nowego sprzętu dla cysterny białej i cysterny B12c (jeśli nie istnieją)
INSERT INTO `sprzet` (`nazwa_unikalna`, `typ_sprzetu`, `pojemnosc_kg`, `stan_sprzetu`, `temperatura_aktualna`, `cisnienie_aktualne`, `ostatnia_aktualizacja`) VALUES
('BIALA', 'cysterna', 15000.00, 'Gotowy', 60.00, 0.00, NOW()),
('CYSTERNA_B12c_DODATKOWA', 'cysterna', 20000.00, 'Gotowy', 60.00, 0.00, NOW()); 