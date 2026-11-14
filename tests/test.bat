@echo off
cd /d "%~dp0.."
echo 1. Full graph
py src\main.py -c tests\test_config.yaml
echo.
echo 2. Max depth 2
py src\main.py -c tests\test_depth.yaml
echo.
echo 3. Filter D
py src\main.py -c tests\test_filter.yaml
echo.
echo 4. Cycle
py src\main.py -c tests\test_cycle.yaml
echo.
echo 5. Unknown package
py src\main.py -c tests\test_error.yaml
echo.
echo 6. Reverse: full
py src\main.py -c tests\test_reverse.yaml
echo.
echo 7. Reverse: max depth 2
py src\main.py -c tests\test_reverse_depth.yaml
echo.
echo 8. Reverse: filter B
py src\main.py -c tests\test_reverse_filter.yaml
echo.
echo 9. Reverse: cycle
py src\main.py -c tests\test_reverse_cycle.yaml
echo.
echo 10. Reverse: no dependents
py src\main.py -c tests\test_reverse_none.yaml
pause