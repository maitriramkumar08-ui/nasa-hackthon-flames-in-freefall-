# Supplied PSI data audit

This audit records what is visible in the files supplied with the project. It is a format audit,
not a claim that every field has been calibrated or scientifically interpreted.

## Metadata archives

| Investigation | File | Observed metadata | Still unresolved |
| --- | --- | --- | --- |
| PSI-25 | `PSI-25_metadata_PSI_metadata_PSI-101_BASS-II.zip` | Study title, approach, DOI `10.60555/4qc4-de67`, `s_PSI-25.txt` member | Complete downloadable measurement-file mapping and channel calibration |
| PSI-69 | `PSI-69_metadata_PSI-133_FLEX.zip` | Study title, approach, DOI `10.60555/mbq8-0451`, `s_PSI-69.txt` member | Complete downloadable measurement-file mapping and channel calibration |
| PSI-98 | `PSI-98_metadata_PSI-166_SAFFIRE-I.zip` | Study title, approach, DOI `10.60555/0t15-1z43`, `s_PSI-98.txt` member | Complete downloadable measurement-file mapping and channel calibration |
| PSI-107 | `PSI-107_metadata_PSI-176_SPICE.zip` | Study title, approach, DOI `10.60555/9kbh-e962`, `s_PSI-107.txt` member | Complete downloadable measurement-file mapping and channel calibration |

The generic ZIP reader exposes these fields without inventing missing investigation IDs or sensor
semantics.

## BASS-II files

`PSI-26_Experimental table_BASS (1).csv` is an experimental index with date, GMT, run/test/sample
numbers, and fuel-sample material. The `BASS-2%20PSI-25%20consolidated%20data%20sheet.xlsx` workbook
contains one `BASS-II Data` sheet with 129 data rows and columns for flow, calibrated initial/final
O₂, initial/final CO₂, and initial/final CO. The workbook also contains missing values and textual
entries such as `none`; these must remain missing rather than becoming zero.

## PSI-159 files

`PSI-159_Raw Data_21235L1_mfcSetpoints.csv` contains one metadata row, a header row, and raw
setpoint values. The reader preserves the controller values in volts and does not convert them to
flow rates because the calibration dictionary is not supplied.

`PSI-159_Raw Data_Final ACME Chamber Calculator - 2021-03-09 to 2021-10-21.xlsx` contains the
`EventData` sheet plus calculator reference sheets. The visible headers identify pressure in psia,
temperature channels in °C, gas-mixture columns, fuel labels, and ignition decisions. The workbook
notes describe `Burn Fraction` as a calculator input/assumption. It is not treated as a direct flame
measurement.

`PSI159_Data_Analysis_Report.docx` says the sensor CSV is raw instrument data and that the complete
channel calibration dictionary is absent. Therefore thermocouple-labelled channels stay raw, PMT and
radiometer amplitudes are not compared directly, and the sensor recording is not linked to an
`EventData` row without confirmed test-point identity.

## Reader boundary

The readers currently implemented are:

- metadata extraction from the four supplied PSI ZIP archives;
- raw PSI-159 setpoint parsing;
- PSI-159 raw condition records that preserve per-row metadata and controller values without
  treating voltages as calibrated flow rates;
- generic local CSV parsing;
- manifest hash verification and explicit reader registration.

Investigation-specific calibrated readers remain intentionally separate from this audit. They need a
channel dictionary, calibration coefficients, and a confirmed file-to-test-point mapping.
